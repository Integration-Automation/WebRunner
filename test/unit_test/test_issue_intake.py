"""Durable issue intake, platform normalization and single-worker claim invariants."""
import json
from dataclasses import replace
from unittest.mock import Mock

import pytest

from je_web_runner.utils.issue_worker.inbox import IssueInbox
from je_web_runner.utils.issue_worker.providers import GitHubIssues, JiraIssues, adf_document, adf_text
from je_web_runner.utils.issue_worker.store import IssueStore
from je_web_runner.utils.issue_worker.types import IssueSnapshot, IssueWorkerConfig, IssueWorkerError, ProviderError
from je_web_runner.utils.issue_worker.http import PlatformClient


def config(tmp_path, **kwargs):
    return IssueWorkerConfig(str(tmp_path), "local-model", "worker-bot", **kwargs)


def snapshot(**kwargs):
    values = dict(source="github", external_id="12", title="Fix behavior", body="Expected behavior and reproduction",
                  url="https://github.com/Integration-Automation/WebRunner/issues/12", labels=("automation-ready",))
    values.update(kwargs)
    return IssueSnapshot(**values)


def test_config_is_closed_and_relative_state_is_resolved(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"state_dir": "state", "model": "local-model", "github_bot": "worker-bot"}))
    assert IssueWorkerConfig.load(path).state_dir == str(tmp_path / "state")
    with pytest.raises(IssueWorkerError):
        config(tmp_path, repository="other/repository")
    with pytest.raises(IssueWorkerError):
        config(tmp_path, timeout=float("nan"))
    with pytest.raises(IssueWorkerError):
        config(tmp_path, jira_url="https://jira.example.test")


def test_snapshot_revision_ignores_ownership_and_bot_labels():
    original = snapshot()
    claimed = replace(original, assignee="worker-bot", labels=("automation-ready", "automation-running"))
    assert claimed.revision == original.revision
    assert claimed.eligible("worker-bot", resume=True)
    assert not claimed.eligible("worker-bot")
    assert not replace(original, assignee="human").eligible("worker-bot", resume=True)
    assert not replace(original, labels=()).eligible("worker-bot")
    assert replace(original, body="changed requirements").revision != original.revision


def test_queue_is_idempotent_and_preserves_checkpoint_across_restart(tmp_path):
    store = IssueStore(tmp_path)
    assert store.enqueue(snapshot())
    assert not store.enqueue(snapshot(body="edited while running"))
    store.save("github:12", "fixing", {"base_sha": "base", "tool_count": 4})
    restarted = IssueStore(tmp_path)
    job = restarted.next_job()
    assert job["status"] == "fixing"
    assert job["data"]["tool_count"] == 4
    assert job["snapshot"]["body"] == snapshot().body


def test_lease_excludes_other_worker_and_cannot_be_borrowed(tmp_path):
    first, second = IssueStore(tmp_path), IssueStore(tmp_path)
    with first.lease():
        first.assert_lease()
        with pytest.raises(IssueWorkerError, match="active"):
            with second.lease():
                pytest.fail("second worker entered a held lease")
        with pytest.raises(IssueWorkerError, match="expired"):
            second.assert_lease()
    with second.lease():
        second.assert_lease()


def test_crashed_lease_can_be_recovered(tmp_path):
    store = IssueStore(tmp_path)
    with store.connection() as connection:
        connection.execute("INSERT INTO lease VALUES(1,'abandoned',0)")
    with store.lease():
        store.assert_lease()


def test_explicit_retry_preserves_history_identity_and_refreshes_requirements(tmp_path):
    store = IssueStore(tmp_path)
    store.enqueue(snapshot())
    store.save("github:12", "failed", {"reason": "failed checks"})
    store.retry(snapshot(body="clarified requirements"))
    job = store.next_job()
    assert job["run"] == 2
    assert job["snapshot"]["body"] == "clarified requirements"
    assert job["data"] == {}
    with pytest.raises(IssueWorkerError):
        store.retry(snapshot())


def test_intake_dry_run_and_manual_enqueue_are_side_effect_free_on_platform(tmp_path):
    provider = Mock(bot="worker-bot")
    provider.scan.return_value = [snapshot()]
    provider.fetch.return_value = snapshot()
    inbox = IssueInbox(config(tmp_path), {"github": provider})
    assert inbox.discover(dry_run=True)[0]["queued"] is False
    assert inbox.store.status() == []
    assert inbox.enqueue("github:12")
    assert not inbox.enqueue("github:12")
    provider.claim.assert_not_called()
    provider.report.assert_not_called()


def test_github_scan_excludes_pull_requests_and_human_owners(tmp_path):
    client = Mock()
    client.session.headers = {}
    client.request.return_value = [{"number": 1, "pull_request": {}, "assignees": []},
                                   {"number": 2, "assignees": [{"login": "human"}]}]
    provider = GitHubIssues(config(tmp_path), client)
    assert list(provider.scan()) == []
    assert client.request.call_count == 1


def test_github_fetch_ignores_bot_progress_in_revision(tmp_path):
    client = Mock()
    client.session.headers = {}
    issue = {"title": "Bug", "body": "Reproduce it", "state": "open", "html_url": "https://example.test/12",
             "assignees": [], "labels": [{"name": "automation-ready"}]}
    client.request.side_effect = [issue, [{"body": "progress", "user": {"login": "worker-bot"}},
                                         {"body": "acceptance", "user": {"login": "human"}}]]
    result = GitHubIssues(config(tmp_path), client).fetch("12")
    assert "progress" not in result.body
    assert "acceptance" in result.body


def test_jira_search_uses_enhanced_pagination_and_project_allowlist(tmp_path):
    settings = config(tmp_path, jira_url="https://jira.example.test", jira_projects=["WR"], jira_bot="account")
    client = Mock()
    client.request.side_effect = [{"issues": [], "nextPageToken": "next"}, {"issues": [], "isLast": True}]
    provider = JiraIssues(settings, client)
    assert list(provider.scan()) == []
    assert all(call.args[1] == "/rest/api/3/search/jql" for call in client.request.call_args_list)
    assert client.request.call_args.kwargs["payload"]["nextPageToken"] == "next"
    with pytest.raises(IssueWorkerError, match="allowlist"):
        provider.fetch("OTHER-12")
    assert adf_text(adf_document("plain text")) == "plain text"


def test_http_mutations_are_not_retried_or_redirected():
    session = Mock()
    response = Mock(status_code=302, is_redirect=True, headers={})
    session.request.return_value = response
    client = PlatformClient("http://127.0.0.1:8080", session)
    with pytest.raises(ProviderError, match="redirect"):
        client.request("POST", "/resource", payload={})
    assert session.request.call_count == 1
    assert session.request.call_args.kwargs["allow_redirects"] is False


def test_last_quota_response_is_accepted_and_next_limit_is_deferred():
    response = Mock(status_code=200, is_redirect=False, headers={"X-RateLimit-Remaining": "0"})
    PlatformClient._check(response)
    response.status_code = 429
    response.headers = {"Retry-After": "123"}
    with pytest.raises(ProviderError) as error:
        PlatformClient._check(response)
    assert error.value.retry_after == 123


def test_github_pagination_detects_repeated_pages_instead_of_looping(tmp_path):
    client = Mock()
    client.session.headers = {}
    client.request.return_value = [{"id": index} for index in range(100)]
    provider = GitHubIssues(config(tmp_path), client)
    with pytest.raises(IssueWorkerError, match="repeated"):
        list(provider._pages(provider.prefix + "/issues"))
    assert client.request.call_count == 2


def test_jira_pagination_detects_multi_page_token_cycles(tmp_path):
    settings = config(tmp_path, jira_url="https://jira.example.test", jira_projects=["WR"], jira_bot="account")
    client = Mock()
    client.request.side_effect = [{"issues": [], "nextPageToken": token} for token in ("a", "b", "a")]
    with pytest.raises(IssueWorkerError, match="repeated"):
        list(JiraIssues(settings, client).scan())
    assert client.request.call_count == 3
