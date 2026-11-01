"""Issue lifecycle, source authorization changes and resumable reviewed publication."""
import time
from dataclasses import replace
from unittest.mock import Mock

import pytest

from test_issue_coding import PATCH
from je_web_runner.utils.issue_worker.planner import CodeAction
from je_web_runner.utils.issue_worker.processor import CodeProcessor
from je_web_runner.utils.issue_worker.publisher import GitHubPublisher
from je_web_runner.utils.issue_worker.types import IssueSnapshot, IssueWorkerError, ProviderError
from je_web_runner.utils.issue_worker.worker import IssueWorker
from je_web_runner.utils.issue_worker.workspace import IssueWorkspace


class FixtureProvider:
    bot = "worker-bot"

    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.claims = 0
        self.reports = []
        self.fail_final = False

    def scan(self):
        return [self.snapshot] if self.snapshot.eligible(self.bot) else []

    def fetch(self, external_id):
        return self.snapshot

    def claim(self, snapshot):
        self.claims += 1
        self.snapshot = replace(self.snapshot, assignee=self.bot)

    def report(self, snapshot, status, message):
        self.reports.append((status, message))
        if status in {"awaiting_review", "failed", "needs_info", "cancelled"}:
            self.snapshot = replace(self.snapshot, labels=())
            if self.fail_final:
                self.fail_final = False
                raise ProviderError("progress reply lost", retry_after=60)

    def close(self):
        return


def worker_for(issue_workspace):
    isolated, job, original = issue_workspace
    provider = FixtureProvider(IssueSnapshot(**job["snapshot"]))
    planner = Mock()
    planner.plan.side_effect = [CodeAction("patch", text=PATCH), CodeAction("finish", summary="Return two")]
    sandbox = Mock()
    sandbox.check.side_effect = lambda root, name, timeout: {
        "name": name, "passed": True, "tree": root.fingerprint(), "output": "passed",
    }
    processor = CodeProcessor(isolated.config, planner, sandbox)
    publisher = Mock()
    publisher.publish.return_value = {"url": "https://example.test/pull/40", "number": 40}
    worker = IssueWorker(isolated.config, {"github": provider}, processor, publisher,
                         lambda config, queued: IssueWorkspace.prepare(config, queued, remote=str(original)))
    return worker, provider, planner, publisher


def test_full_local_lifecycle_ends_with_review_not_issue_closure(issue_workspace):
    worker, provider, planner, publisher = worker_for(issue_workspace)
    try:
        result = worker.run_once()
        assert result["status"] == "awaiting_review"
        assert result["data"]["pr"]["number"] == 40
        assert result["data"]["report_pending"] is False
        assert provider.claims == 1
        assert provider.snapshot.closed is False
        assert worker.run_once()["status"] == "idle"
        assert planner.plan.call_count == 2
        assert publisher.publish.call_count == 1
    finally:
        worker.close()


def test_removed_ready_label_cancels_before_patch_or_publication(issue_workspace):
    worker, provider, planner, publisher = worker_for(issue_workspace)

    def remove_label(context, timeout):
        provider.snapshot = replace(provider.snapshot, labels=())
        return CodeAction("patch", text=PATCH)

    planner.plan.side_effect = remove_label
    try:
        result = worker.run_once()
        assert result["status"] == "cancelled"
        assert issue_workspace[0].changes() == []
        publisher.publish.assert_not_called()
    finally:
        worker.close()


@pytest.mark.parametrize("change", ["requirements", "manual_hold", "owner", "ready_label"])
def test_analysis_rechecks_source_changes_before_returning_questions(issue_workspace, change):
    worker, provider, planner, publisher = worker_for(issue_workspace)
    worker.config.requirements_enabled = True
    analyzer = Mock()

    def changed_during_analysis(_snapshot, _feedback, _timeout):
        changes = {"requirements": {"body": "A revised requirement"},
                   "manual_hold": {"labels": ("automation-ready", "automation-manual")},
                   "owner": {"assignee": "human"}, "ready_label": {"labels": ()}}
        provider.snapshot = replace(provider.snapshot, **changes[change])
        return {"summary": "Clarify behavior", "kind": "bug", "criteria": [],
                "questions": ["Which input should change?"], "revision": "fixture"}

    analyzer.analyze.side_effect = changed_during_analysis
    worker.processor.analyzer = analyzer
    try:
        result = worker.run_once()
        assert result["status"] == "cancelled"
        worker.processor.sandbox.check.assert_not_called()
        planner.plan.assert_not_called()
        publisher.publish.assert_not_called()
    finally:
        worker.close()


def test_model_or_sandbox_unavailable_does_not_claim_an_issue(issue_workspace):
    worker, provider, _planner, publisher = worker_for(issue_workspace)
    worker.processor.preflight = Mock(side_effect=IssueWorkerError("Podman image unavailable"))
    try:
        result = worker.run_once()
        assert result["status"] == "failed"
        assert provider.claims == 0
        assert provider.reports == []
        publisher.publish.assert_not_called()
    finally:
        worker.close()


def test_final_progress_outbox_recovers_without_recoding_or_republishing(issue_workspace):
    worker, provider, planner, publisher = worker_for(issue_workspace)
    provider.fail_final = True
    try:
        result = worker.run_once()
        assert result["status"] == "awaiting_review"
        assert result["data"]["report_pending"] is True
        worker.store.save(result["key"], result["status"], result["data"])
        recovered = worker.run_once(discover=False)
        assert recovered["data"]["report_pending"] is False
        assert planner.plan.call_count == 2
        assert publisher.publish.call_count == 1
    finally:
        worker.close()


def publication(issue_workspace):
    isolated, job, _original = issue_workspace
    isolated.patch(PATCH)
    tree = isolated.fingerprint()
    job["created"] = time.time()
    job["data"] = {"validated_tree": tree, "deadline": time.time() + 60,
                   "checks": {"unit": {"passed": True, "tree": tree}}, "summary": "Return two"}
    provider = Mock(config=isolated.config, prefix="/repos/Integration-Automation/WebRunner")
    calls = []

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path.endswith("/pulls"):
            return [] if method == "GET" else {"number": 40, "html_url": "https://example.test/pull/40"}
        if "/git/commits/" in path:
            return {"tree": {"sha": "original-tree"}}
        if path.endswith("/git/trees"):
            return {"sha": tree}
        if path.endswith("/git/commits"):
            return {"sha": "remote-commit"}
        if path.endswith("/git/ref/heads/dev"):
            return {"object": {"sha": isolated.base_sha}}
        if "/git/ref/" in path:
            return None
        if path.endswith("/git/refs"):
            return {"ref": "created"}
        raise AssertionError((method, path))

    provider.client.request.side_effect = request
    return GitHubPublisher(provider), job, calls


def test_publisher_sends_exact_validated_content_and_no_merge_request(issue_workspace):
    publisher, job, calls = publication(issue_workspace)
    result = publisher.publish(issue_workspace[0], job, lambda status, data: None)
    assert result["number"] == 40
    tree_request = next(kwargs["payload"] for method, path, kwargs in calls if path.endswith("/git/trees"))
    assert tree_request["tree"][0]["content"] == "def value():\n    return 2\n"
    pr_request = next(kwargs["payload"] for method, path, kwargs in calls
                      if path.endswith("/pulls") and method == "POST")
    assert pr_request["base"] == "dev"
    assert pr_request["head"] == "automation/github-12-r1"
    assert "Closes" not in pr_request["body"]
    assert not any("/merge" in path for _method, path, _kwargs in calls)


def test_uncertain_pr_response_is_reconciled_before_any_new_writes(issue_workspace):
    publisher, job, _calls = publication(issue_workspace)
    job["data"]["remote_commit"] = "remote-commit"
    publisher.client.request.side_effect = None
    publisher.client.request.return_value = [{
        "body": "<!-- webrunner-issue:github:12:run-1 -->", "user": {"login": "worker-bot"},
        "state": "open", "html_url": "https://example.test/pull/40", "number": 40,
        "head": {"sha": "remote-commit"},
    }]
    result = publisher.publish(issue_workspace[0], job, lambda status, data: None)
    assert result["number"] == 40
    assert publisher.client.request.call_count == 1
    assert publisher.client.request.call_args.args[0] == "GET"


def test_modified_tree_cannot_reuse_old_validation(issue_workspace):
    publisher, job, _calls = publication(issue_workspace)
    job["data"]["validated_tree"] = "stale-tree"
    with pytest.raises(IssueWorkerError, match="validated"):
        publisher.publish(issue_workspace[0], job, lambda status, data: None)


def test_state_directory_cannot_switch_jira_site(issue_workspace):
    worker, _provider, _planner, _publisher = worker_for(issue_workspace)
    try:
        with pytest.raises(IssueWorkerError, match="scope"):
            worker.store.bind({"repository": "other", "github_api": "", "jira_url": ""})
    finally:
        worker.close()


def test_explicit_retry_can_reclaim_our_bot_assignment_with_fresh_requirements(issue_workspace):
    worker, provider, planner, publisher = worker_for(issue_workspace)
    planner.plan.side_effect = [CodeAction("needs_info", summary="Which return value is expected?")]
    try:
        first = worker.run_once()
        assert first["status"] == "needs_info"
        provider.snapshot = replace(provider.snapshot, labels=("automation-ready",), body="Return two.")
        worker.retry(first["key"])
        planner.plan.side_effect = [CodeAction("patch", text=PATCH), CodeAction("finish", summary="Return two")]
        recovered = worker.run_once(discover=False)
        assert recovered["status"] == "awaiting_review"
        assert recovered["run"] == 2
        assert provider.claims == 2
        publisher.publish.assert_called_once()
    finally:
        worker.close()


def test_publisher_rejects_a_dev_baseline_that_advanced(issue_workspace):
    publisher, job, calls = publication(issue_workspace)
    original = publisher.client.request.side_effect

    def advanced(method, path, **kwargs):
        if path.endswith("/git/ref/heads/dev"):
            return {"object": {"sha": "new-baseline"}}
        return original(method, path, **kwargs)

    publisher.client.request.side_effect = advanced
    with pytest.raises(IssueWorkerError, match="dev advanced"):
        publisher.publish(issue_workspace[0], job, lambda status, data: None)
    assert not any(method == "POST" for method, _path, _kwargs in calls)
