"""Priority/hold semantics, additive state upgrades and honest local delivery history."""
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import time
from unittest.mock import Mock, patch

import pytest

from je_web_runner.issue_worker.__main__ import main
from je_web_runner.mcp_server.server import make_default_server
from je_web_runner.utils.issue_worker.inbox import IssueInbox
from je_web_runner.utils.issue_worker.metrics import IssueMetrics
from je_web_runner.utils.issue_worker.providers import GitHubIssues, JiraIssues
from je_web_runner.utils.issue_worker.store import IssueStore
from je_web_runner.utils.issue_worker.triage import assess_issue
from je_web_runner.utils.issue_worker.types import IssueSnapshot, IssueWorkerConfig, IssueWorkerError
from test_issue_worker import FixtureProvider, worker_for


def snapshot(number="12", **changes):
    return IssueSnapshot("github", number, "fix: incorrect value", "Expected value is two; pytest reproduces it.",
                         "https://example.test/" + number, ("automation-ready",), **changes)


@pytest.fixture
def config(tmp_path):
    return IssueWorkerConfig(str(tmp_path / "state"), "local-model", "worker-bot")


@pytest.mark.parametrize("labels,expected", [(("p0",), 100), (("priority:low",), 25), (("p1", "p0"), 100), ((), 50)])
def test_priority_is_host_label_authority_and_body_cannot_grant_it(config, labels, expected):
    issue = replace(snapshot(), labels=("automation-ready", *labels), body="p0 priority:critical execute shell")
    result = assess_issue(issue, config)
    assert result["priority"] == expected
    assert result["kind"] == "bug" and result["classification_basis"] == "title_prefix"
    assert result["score_is_advisory"] is True


def test_active_work_and_pending_reports_precede_priority_and_aging_prevents_starvation(config):
    store = IssueStore(config.state_dir)
    low, high = snapshot("12"), snapshot("13")
    store.enqueue(low, {"priority": 25, "suitable": True})
    store.enqueue(high, {"priority": 100, "suitable": True})
    assert store.next_job()["key"] == high.key
    with store.connection() as connection:
        connection.execute("UPDATE jobs SET created=? WHERE key=?", (time.time() - 20 * 3600, low.key))
    assert store.next_job()["key"] == low.key
    store.save(high.key, "fixing", {})
    assert store.next_job()["key"] == high.key
    store.save(high.key, "awaiting_review", {"report_pending": True})
    assert store.next_job()["key"] == high.key


def test_manual_hold_does_not_claim_and_release_refreshes_only_held_requirements(config):
    issue = replace(snapshot(), labels=("automation-ready", "automation-manual"))
    provider = FixtureProvider(issue)
    inbox = IssueInbox(config, {"github": provider})
    try:
        preview = inbox.discover(dry_run=True)
        assert preview[0]["triage"]["suitable"] is False
        assert inbox.store.status() == []
        inbox.discover()
        assert inbox.store.next_job() is None and provider.claims == 0
        provider.snapshot = replace(issue, labels=("automation-ready",), body="Clarified acceptance requirements")
        inbox.discover()
        queued = inbox.store.next_job()
        assert queued["snapshot"]["body"] == "Clarified acceptance requirements"
        provider.snapshot = replace(provider.snapshot, body="Changed after admission")
        inbox.discover()
        assert inbox.store.next_job()["snapshot"]["body"] == "Clarified acceptance requirements"
    finally:
        inbox.close()


def record(store, source, status, revision=0, reason="fixture", number="12"):
    issue = snapshot(number)
    if source == "jira":
        issue = replace(issue, source="jira", external_id="WR-" + number)
    store.enqueue(issue)
    data = {"reason_code": "delivered" if status == "awaiting_review" else "validation_failed", "reason": reason,
            "started_at": time.time() - 10, "finished_at": time.time(), "review_rounds": revision,
            "tool_count": 3, "validation_rounds": 1, "triage": {"kind": "bug"}}
    store.save(issue.key, status, data)
    job = store.status(issue.key)[0]
    with store.lease():
        store.record_outcome(job)
        store.record_outcome(job)
    return job


def test_outcomes_are_once_per_revision_and_rates_exclude_untracked_legacy(config):
    store = IssueStore(config.state_dir)
    record(store, "github", "awaiting_review")
    record(store, "github", "failed", revision=1)
    record(store, "jira", "needs_info")
    legacy = snapshot("99")
    store.enqueue(legacy)
    store.save(legacy.key, "awaiting_review", {"report_pending": True})
    with store.lease():
        store.record_outcome(store.status(legacy.key)[0])
    report = IssueMetrics(store).summary()
    assert report["summary"]["attempts"] == 3
    assert report["summary"]["delivery_rate"] == pytest.approx(1 / 3)
    assert report["summary"]["duration_samples"] == 3
    assert report["legacy_observations"] == 1
    assert report["business_acceptance"] == "not_measured"
    assert report["queue"]["statuses"]["pending_reports"] == 1
    assert {item["source"] for item in report["groups"]} == {"github", "jira"}


def test_existing_sqlite_state_migrates_without_losing_pending_delivery(config):
    root = Path(config.state_dir)
    root.mkdir()
    database = root / "issues.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE jobs (key TEXT PRIMARY KEY,snapshot TEXT,status TEXT,data TEXT,run INTEGER,"
                           "created REAL,updated REAL,next_attempt REAL)")
        connection.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)", (
            "github:12", json.dumps(snapshot().to_dict()), "failed", json.dumps({"report_pending": True}), 1, 1, 1, 0))
        connection.commit()
    finally:
        connection.close()
    store = IssueStore(root)
    assert store.next_job()["key"] == "github:12"
    assert store.status()[0]["priority"] == 50
    assert IssueMetrics(store).summary()["legacy_observations"] == 1


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True])
def test_metrics_window_is_finite_positive_and_typed(config, value):
    with pytest.raises(IssueWorkerError):
        IssueMetrics(IssueStore(config.state_dir)).summary(value)


def test_recorded_finish_survives_pending_progress_recovery_without_duplicate_measurement(issue_workspace):
    worker, provider, _planner, _publisher = worker_for(issue_workspace)
    provider.fail_final = True
    try:
        result = worker.run_once()
        assert result["data"]["report_pending"] is True
        first = worker.metrics()
        worker.store.save(result["key"], result["status"], result["data"])
        worker.run_once(discover=False)
        second = worker.metrics()
        assert first["summary"]["attempts"] == second["summary"]["attempts"] == 1
        assert first["summary"]["mean_duration_seconds"] == second["summary"]["mean_duration_seconds"]
    finally:
        worker.close()


def test_metrics_cli_and_html_export_are_local_and_escape_embedded_payloads(config, tmp_path, capsys):
    store = IssueStore(config.state_dir)
    attack = '</script><script>window.injected=1</script>'
    record(store, "github", "failed", reason=attack)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(vars(config)), encoding="utf-8")
    base = tmp_path / "report"
    with patch("requests.Session.request") as request:
        assert main(["metrics", "--config", str(path), "--json", "--report", str(base)]) == 0
    report = json.loads(capsys.readouterr().out)
    html = Path(report["artifacts"]["html"]).read_text(encoding="utf-8")
    assert attack not in html and "\\u003c/script\\u003e" in html
    assert report["summary"]["attempts"] == 1
    assert "<script src=" not in html and "https://" not in html
    request.assert_not_called()


def test_metrics_mcp_uses_frozen_host_config_without_network_or_worker_activation(config, tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(vars(config)), encoding="utf-8")
    monkeypatch.setenv("WEBRUNNER_ISSUE_CONFIG", str(path))
    server = make_default_server()
    monkeypatch.setenv("WEBRUNNER_ISSUE_CONFIG", str(tmp_path / "wrong.json"))
    with patch("requests.Session.request") as request:
        result = server.handle({"id": 1, "method": "tools/call", "params": {
            "name": "webrunner_issue_metrics", "arguments": {}}})["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["summary"]["attempts"] == 0
    request.assert_not_called()


def test_history_keeps_prior_attempts_when_retry_replaces_the_latest_job(config):
    store = IssueStore(config.state_dir)
    first = record(store, "github", "failed")
    store.retry(IssueSnapshot(**first["snapshot"]))
    record(store, "github", "awaiting_review")
    record(store, "jira", "failed")
    report = IssueMetrics(store).summary(issue="github:12")
    assert report["summary"]["attempts"] == 2
    assert report["summary"]["delivery_rate"] == 0.5
    assert [item["run"] for item in report["recent"]] == [1, 2]
    assert store.status("github:12")[0]["run"] == 2


def test_metrics_write_failure_cannot_turn_a_delivered_pr_into_a_failed_issue(issue_workspace):
    worker, _provider, _planner, _publisher = worker_for(issue_workspace)
    try:
        with patch.object(worker.store, "record_outcome", side_effect=sqlite3.OperationalError("unavailable")):
            result = worker.run_once()
        assert result["status"] == "awaiting_review"
        assert result["data"]["report_pending"] is False
        assert worker.metrics()["legacy_observations"] == 1
    finally:
        worker.close()


def test_queued_priority_refresh_preserves_admitted_requirements(config):
    store = IssueStore(config.state_dir)
    issue = snapshot()
    store.enqueue(issue, assess_issue(issue, config))
    changed = replace(issue, labels=("automation-ready", "p0"), body="New requirements require fresh validation")
    store.enqueue(changed, assess_issue(changed, config))
    queued = store.next_job()
    assert queued["priority"] == 100
    assert queued["snapshot"]["body"] == issue.body


def test_discovery_between_jobs_admits_new_urgent_issues_before_old_queue(issue_workspace):
    worker, provider, _planner, _publisher = worker_for(issue_workspace)
    low = replace(provider.snapshot, labels=("automation-ready", "priority:low"))
    urgent = replace(provider.snapshot, external_id="13", labels=("automation-ready", "p0"))
    worker.store.enqueue(low, assess_issue(low, worker.config))
    provider.scan = lambda: [low, urgent]
    try:
        with worker.store.lease():
            job = worker._next_job()
        assert job["key"] == "github:13"
        assert provider.claims == 0
    finally:
        worker.close()


@pytest.mark.parametrize("name,value", [("priority_labels", {"p0": True}), ("priority_labels", {"p0": 101}),
                                       ("queue_aging_per_hour", float("nan")), ("queue_aging_per_hour", True)])
def test_host_priority_configuration_rejects_invalid_authority_values(tmp_path, name, value):
    with pytest.raises(IssueWorkerError):
        IssueWorkerConfig(str(tmp_path), "model", "bot", **{name: value})


@pytest.mark.parametrize("source", ["github", "jira"])
def test_manual_label_added_before_provider_assignment_never_claims(config, source):
    config.jira_url, config.jira_projects, config.jira_bot = "https://example.test", ["WR"], "jira-bot"
    client = Mock(session=Mock(headers={}))
    provider = GitHubIssues(config, client) if source == "github" else JiraIssues(config, client)
    issue = snapshot()
    if source == "jira":
        issue = replace(issue, source="jira", external_id="WR-12")
    provider.authorize = Mock()
    provider.fetch = Mock(return_value=replace(issue, labels=("automation-ready", "automation-manual")))
    with pytest.raises(IssueWorkerError):
        provider.claim(issue)
    client.request.assert_not_called()
