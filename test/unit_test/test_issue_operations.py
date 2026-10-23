"""Readiness, fenced daemon ownership, outage recovery and cooperative drain behavior."""
import json
import sqlite3
import threading
import time
from unittest.mock import Mock, patch

import pytest

from je_web_runner.issue_worker.__main__ import main, _watch
from je_web_runner.utils.issue_worker.doctor import IssueDoctor
from je_web_runner.utils.issue_worker.runtime import WorkerRuntime, operational_log
from je_web_runner.utils.issue_worker.sandbox import PodmanSandbox
from je_web_runner.utils.issue_worker.store import IssueStore
from je_web_runner.utils.issue_worker.types import EnvironmentUnavailable, IssueWorkerConfig, IssueWorkerError
from test_issue_worker import worker_for


@pytest.fixture
def settings(tmp_path):
    return IssueWorkerConfig(str(tmp_path / "state"), "installed-model", "worker-bot")


def test_doctor_state_checks_do_not_create_a_queue(settings):
    doctor = IssueDoctor(settings)
    doctor._state()
    from pathlib import Path
    assert not (Path(settings.state_dir) / "issues.sqlite3").exists()
    assert list(Path(settings.state_dir).iterdir()) == []


def test_doctor_checks_existing_database_without_changing_jobs(settings):
    store = IssueStore(settings.state_dir)
    IssueDoctor(settings)._state()
    assert store.status() == []
    store.path.write_bytes(b"corrupt database")
    with pytest.raises(sqlite3.DatabaseError):
        IssueDoctor(settings)._state()


@pytest.mark.parametrize("error", [OSError("host-secret"), sqlite3.OperationalError("host-secret")])
def test_diagnostics_hide_exception_details_and_continue(settings, error):
    doctor = IssueDoctor(settings)
    with patch.object(doctor, "_git", side_effect=error), patch.object(doctor, "_state"), \
            patch.object(doctor, "_ollama"), patch("je_web_runner.utils.issue_worker.doctor.PodmanSandbox"):
        report = doctor.check()
    assert report["ready"] is False
    assert len(report["checks"]) == 4
    assert "host-secret" not in json.dumps(report)
    assert report["checks"][0]["code"] == "git_unavailable"


def test_local_diagnostics_never_contact_platforms(settings):
    doctor = IssueDoctor(settings)
    with patch.object(doctor, "_git"), patch.object(doctor, "_state"), patch.object(doctor, "_ollama"), \
            patch("je_web_runner.utils.issue_worker.doctor.PodmanSandbox"), \
            patch("je_web_runner.utils.issue_worker.doctor.GitHubIssues") as github:
        assert doctor.check()["ready"] is True
    github.assert_not_called()


def test_platform_diagnostics_use_get_only_and_do_not_claim(settings, monkeypatch):
    settings.jira_url, settings.jira_projects, settings.jira_bot = "https://example.test", ["WR"], "jira-bot"
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-token")
    monkeypatch.setenv("JIRA_EMAIL", "fixture@example.test")
    monkeypatch.setenv("JIRA_API_TOKEN", "fixture-jira-token")
    calls = []

    def request(_client, method, path, **_kwargs):
        calls.append((method, path))
        return {"login": "worker-bot", "accountId": "jira-bot"}

    doctor = IssueDoctor(settings)
    with patch.object(doctor, "_git"), patch.object(doctor, "_state"), patch.object(doctor, "_ollama"), \
            patch("je_web_runner.utils.issue_worker.doctor.PodmanSandbox"), \
            patch("je_web_runner.utils.issue_worker.http.PlatformClient.request", request):
        report = doctor.check(include_platform=True)
    assert report["ready"] is True
    assert all(method == "GET" for method, _path in calls)
    assert sum("/labels/" in path for _method, path in calls) == 6
    assert ("GET", "/rest/api/3/project/WR") in calls
    assert report["checks"][-1]["status"] == "unverified"


def test_daemon_ownership_is_exclusive_and_stop_is_instance_bound(settings):
    first = WorkerRuntime(IssueStore(settings.state_dir))
    second = WorkerRuntime(IssueStore(settings.state_dir))
    assert second.request_stop() is False
    with first.own():
        token = first.token
        with pytest.raises(IssueWorkerError, match="another watch"):
            with second.own():
                pytest.fail("a second watch must not start")
        assert second.request_stop() is True
        assert first.stopping() is True
        assert first.health()["status"] == "healthy"
    assert second.health()["status"] == "stopped"
    assert second.request_stop() is False
    with second.own():
        assert second.token != token
        assert second.stopping() is False


def test_watch_refuses_to_start_while_manual_job_is_running(settings):
    store = IssueStore(settings.state_dir)
    with store.lease(), pytest.raises(IssueWorkerError, match="job is active"):
        with WorkerRuntime(store).own():
            pytest.fail("manual job lease must block watch acquisition")


def test_stale_owner_cannot_write_after_a_successor_takes_over(settings):
    store = IssueStore(settings.state_dir)
    first, second = WorkerRuntime(store), WorkerRuntime(store)
    with pytest.raises(IssueWorkerError, match="ownership was lost"), first.own():
        with store.connection() as connection:
            connection.execute("UPDATE worker_runtime SET heartbeat=?", (time.time() - 46,))
        assert second.health()["status"] == "stale"
        assert second.request_stop() is False
        with second.own():
            with pytest.raises(IssueWorkerError, match="ownership was lost"):
                first.update("publishing")


def test_heartbeat_continues_during_long_work(settings, monkeypatch):
    monkeypatch.setattr("je_web_runner.utils.issue_worker.runtime.HEARTBEAT_SECONDS", 0.02)
    runtime = WorkerRuntime(IssueStore(settings.state_dir))
    with runtime.own():
        initial = runtime.health()["heartbeat"]
        deadline = time.monotonic() + 2
        while runtime.health()["heartbeat"] == initial and time.monotonic() < deadline:
            threading.Event().wait(0.01)
        assert runtime.health()["heartbeat"] > initial


def test_watch_drains_after_the_current_issue_and_does_not_start_another(issue_workspace):
    worker, provider, planner, publisher = worker_for(issue_workspace)
    original = planner.plan.side_effect
    actions = iter(original)

    def stop_during_code(_context, _timeout):
        assert worker.request_stop() is True
        return next(actions)

    planner.plan.side_effect = stop_during_code
    try:
        with patch("je_web_runner.utils.issue_worker.worker.IssueDoctor") as doctor:
            doctor.return_value.check.return_value = {"ready": True}
            worker.watch()
        assert provider.claims == 1
        assert publisher.publish.call_count == 1
        assert worker.status()[0]["status"] == "awaiting_review"
        assert worker.health()["status"] == "stopped"
    finally:
        worker.close()


def test_dependency_outage_pauses_intake_and_recovers_without_failing_jobs(issue_workspace):
    worker, provider, _planner, _publisher = worker_for(issue_workspace)
    worker.config.poll_seconds = 0.01
    polls = 0

    def readiness():
        nonlocal polls
        polls += 1
        if polls == 1:
            return {"ready": False, "checks": [{"status": "failed", "code": "ollama_unavailable"}]}
        assert provider.claims == 0
        worker.request_stop()
        return {"ready": True}

    try:
        with patch("je_web_runner.utils.issue_worker.worker.IssueDoctor") as doctor:
            doctor.return_value.check.side_effect = readiness
            worker.watch()
        assert polls == 2
        assert worker.status() == []
        assert "intake paused" in (worker.store.root / "logs/worker.log").read_text(encoding="utf-8")
    finally:
        worker.close()


def test_midjob_environment_failure_remains_resumable(issue_workspace):
    worker, provider, _planner, publisher = worker_for(issue_workspace)
    worker.processor.sandbox.check.side_effect = EnvironmentUnavailable("engine stopped")
    try:
        report = worker.run_once()
        assert report["status"] not in {"failed", "cancelled"}
        assert report["data"]["environment_error"]
        assert provider.claims == 1
        publisher.publish.assert_not_called()
    finally:
        worker.close()


def test_operational_log_rotates_without_leaking_context(settings):
    store = IssueStore(settings.state_dir)
    with operational_log(store) as logger:
        logger.handlers[0].maxBytes = 60
        for _index in range(10):
            logger.info("poll completed: idle")
    assert (store.root / "logs/worker.log.1").exists()
    assert not (store.root / "logs/worker.log.6").exists()


def test_cli_health_and_stop_never_make_network_requests(settings, tmp_path, capsys):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(vars(settings)), encoding="utf-8")
    with patch("requests.Session.request") as request:
        assert main(["health", "--config", str(path), "--json"]) == 2
        assert json.loads(capsys.readouterr().out)["status"] == "stopped"
        assert main(["stop", "--config", str(path)]) == 0
        assert json.loads(capsys.readouterr().out) == {"stop_requested": False}
    request.assert_not_called()


def test_first_interrupt_drains_and_second_interrupt_aborts():
    worker = Mock()

    def exercise(stop):
        handler = install.call_args_list[0].args[1]
        handler(2, None)
        assert stop.is_set()
        with pytest.raises(KeyboardInterrupt):
            handler(2, None)

    worker.watch.side_effect = exercise
    with patch("je_web_runner.issue_worker.__main__.signal.signal") as install:
        _watch(worker)
    assert install.call_count == 2


def test_stop_orders_before_next_job_and_does_not_leave_future_flags(settings):
    runtime = WorkerRuntime(IssueStore(settings.state_dir))
    with runtime.own():
        assert runtime.request_stop() is True
        assert runtime.begin_job("github:12") is False
        assert runtime.health()["current_issue"] is None


def test_interrupt_during_discovery_does_not_claim_a_new_job(issue_workspace):
    worker, provider, _planner, publisher = worker_for(issue_workspace)
    stop = threading.Event()
    original_scan = provider.scan

    def scan_then_stop():
        stop.set()
        return original_scan()

    provider.scan = scan_then_stop
    try:
        with patch("je_web_runner.utils.issue_worker.worker.IssueDoctor") as doctor:
            doctor.return_value.check.return_value = {"ready": True}
            worker.watch(stop)
        assert provider.claims == 0
        assert worker.status()[0]["status"] == "queued"
        publisher.publish.assert_not_called()
    finally:
        worker.close()


def test_lost_heartbeat_blocks_further_work(settings):
    runtime = WorkerRuntime(IssueStore(settings.state_dir))
    with pytest.raises(IssueWorkerError, match="ownership was lost"), runtime.own():
        with patch.object(runtime.store, "connection", side_effect=sqlite3.OperationalError("disk unavailable")):
            runtime._renew(Mock(wait=Mock(return_value=False)), runtime.token, runtime.lost)
        assert runtime.lost.is_set()
        with pytest.raises(IssueWorkerError, match="ownership was lost"):
            runtime.begin_job("github:12")


def test_doctor_cli_returns_failed_json_without_constructing_worker(settings, tmp_path, capsys):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(vars(settings)), encoding="utf-8")
    report = {"ready": False, "checks": [{"name": "ollama", "status": "failed",
                                        "code": "ollama_unavailable", "hint": "Install local weights."}]}
    with patch("je_web_runner.issue_worker.__main__.IssueDoctor") as doctor, \
            patch("je_web_runner.issue_worker.__main__.IssueWorker") as worker:
        doctor.return_value.check.return_value = report
        assert main(["doctor", "--config", str(path), "--platform", "--json"]) == 1
        doctor.return_value.check.assert_called_once_with(include_platform=True)
        assert json.loads(capsys.readouterr().out) == report
        worker.assert_not_called()


def test_health_distinguishes_dependency_outage_and_stale_heartbeat(settings):
    runtime = WorkerRuntime(IssueStore(settings.state_dir))
    with runtime.own():
        runtime.update("waiting_dependencies", error="ollama_unavailable")
        assert runtime.health()["status"] == "degraded"
        runtime.update("waiting", polled=True)
        assert runtime.health()["status"] == "healthy"
        assert runtime.health()["last_poll"] > 0


def test_container_recovery_is_scoped_and_refuses_unexpected_names(settings):
    sandbox = PodmanSandbox(settings)
    name = "webrunner-issue-" + "a" * 24
    with patch("je_web_runner.utils.issue_worker.sandbox.subprocess.run") as command:
        command.return_value = Mock(returncode=0, stdout=(name + "\n").encode())
        sandbox.recover()
        assert "label=" + sandbox.label in command.call_args_list[0].args[0]
        assert command.call_args_list[1].args[0][-1] == name
        command.reset_mock()
        command.return_value = Mock(returncode=0, stdout=b"unrelated-container\n")
        with pytest.raises(EnvironmentUnavailable, match="unexpected container name"):
            sandbox.recover()
        assert command.call_count == 1
