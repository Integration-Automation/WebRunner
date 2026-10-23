"""Issue CLI/MCP host configuration, readiness gates and status results."""
import json
from unittest.mock import Mock, patch

import pytest

from je_web_runner.issue_worker.__main__ import main
from je_web_runner.mcp_server.server import make_default_server
from je_web_runner.utils.issue_worker import IssueStore, IssueWorkerConfig


def configuration(tmp_path):
    path = tmp_path / "worker.json"
    path.write_text(json.dumps({"state_dir": "state", "model": "fixture-local", "github_bot": "worker-bot"}),
                    encoding="utf-8")
    return path


@pytest.mark.parametrize("status,code", [("idle", 0), ("awaiting_review", 0), ("failed", 1), ("needs_info", 1)])
def test_issue_cli_exit_codes(status, code, tmp_path, capsys):
    worker = Mock()
    worker.run_once.return_value = {"status": status}
    with patch("je_web_runner.issue_worker.__main__.IssueWorker", return_value=worker):
        assert main(["run", "--config", str(configuration(tmp_path))]) == code
    assert json.loads(capsys.readouterr().out)["status"] == status
    worker.close.assert_called_once()


def test_cli_preview_does_not_activate_coding(tmp_path, capsys):
    worker = Mock()
    worker.run_once.return_value = {"preview": []}
    with patch("je_web_runner.issue_worker.__main__.IssueWorker", return_value=worker):
        assert main(["run", "--dry-run", "--config", str(configuration(tmp_path))]) == 0
    worker.run_once.assert_called_once_with(dry_run=True)
    assert json.loads(capsys.readouterr().out) == {"preview": []}


def test_retry_requires_explicit_issue_key(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["retry", "--config", str(configuration(tmp_path))])
    assert error.value.code == 2


def call_tool(name, arguments):
    return make_default_server().handle({"id": 1, "method": "tools/call", "params": {
        "name": name, "arguments": arguments,
    }})["result"]


def test_mcp_issue_tools_require_host_config(monkeypatch):
    monkeypatch.delenv("WEBRUNNER_ISSUE_CONFIG", raising=False)
    result = call_tool("webrunner_issue_enqueue", {"issue": "github:12"})
    assert result["isError"] is True
    assert "WEBRUNNER_ISSUE_CONFIG" in result["content"][0]["text"]


def test_mcp_caller_cannot_override_configuration(monkeypatch):
    monkeypatch.delenv("WEBRUNNER_ISSUE_CONFIG", raising=False)
    result = call_tool("webrunner_issue_enqueue", {"issue": "github:12", "config": "untrusted.json"})
    assert result["isError"] is True
    assert "config" in result["content"][0]["text"]


def test_mcp_status_reads_local_state_without_platform_requests(tmp_path, monkeypatch):
    path = configuration(tmp_path)
    monkeypatch.setenv("WEBRUNNER_ISSUE_CONFIG", str(path))
    store = IssueStore(IssueWorkerConfig.load(path).state_dir)
    with patch("requests.Session.request") as network:
        result = call_tool("webrunner_issue_status", {})
    assert result["isError"] is False
    assert result["structuredContent"] == {"jobs": []}
    assert store.status() == []
    network.assert_not_called()


def test_mcp_enqueue_does_not_start_a_coding_worker(tmp_path, monkeypatch):
    path = configuration(tmp_path)
    monkeypatch.setenv("WEBRUNNER_ISSUE_CONFIG", str(path))
    inbox = Mock()
    inbox.enqueue.return_value = True
    with patch("je_web_runner.mcp_server.issue_tools.IssueInbox", return_value=inbox), \
            patch("je_web_runner.utils.issue_worker.worker.IssueWorker.run_once") as execute:
        result = call_tool("webrunner_issue_enqueue", {"issue": "github:12"})
    assert result["isError"] is False
    assert result["structuredContent"]["queued"] is True
    inbox.enqueue.assert_called_once_with("github:12")
    execute.assert_not_called()


def test_mcp_host_config_is_frozen_before_any_tool_can_change_environment(tmp_path, monkeypatch):
    path = configuration(tmp_path)
    monkeypatch.setenv("WEBRUNNER_ISSUE_CONFIG", str(path))
    server = make_default_server()
    # Other tools may load environment files; they cannot redirect issue tools or replace their parsed settings.
    monkeypatch.setenv("WEBRUNNER_ISSUE_CONFIG", str(tmp_path / "untrusted.json"))
    path.write_text("{}", encoding="utf-8")
    result = server.handle({"id": 1, "method": "tools/call", "params": {
        "name": "webrunner_issue_status", "arguments": {},
    }})["result"]
    assert result["isError"] is False
    assert result["structuredContent"] == {"jobs": []}
