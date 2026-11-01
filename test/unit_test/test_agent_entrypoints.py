"""CLI/MCP error semantics, host-controlled secrets and local report safety."""
import json
from unittest.mock import patch

import pytest

from je_web_runner.mcp_server.server import make_default_server
from je_web_runner.utils.agent import AgentReport
from je_web_runner.utils.agent.report import write_agent_report
from je_web_runner.utils.cli.cli_main import main


def task_json():
    return {"goal": "Check a result", "start_url": "http://localhost/demo",
            "success": [{"kind": "text_contains", "value": "finished"}]}


def call_tool(name, arguments):
    return make_default_server().handle({"id": 1, "method": "tools/call", "params": {
        "name": name, "arguments": arguments,
    }})["result"]


@pytest.mark.parametrize("status,expected", [("success", 0), ("failed", 1), ("timeout", 1)])
def test_cli_exit_code_and_report(status, expected, tmp_path, capsys):
    path = tmp_path / "task.json"
    path.write_text(json.dumps(task_json()), encoding="utf-8")
    report = AgentReport(status=status, stopped_reason="測試 <script>alert(1)</script>")
    with patch("je_web_runner.utils.agent.run_agent", return_value=report):
        assert main(["--agent-task", str(path), "--report", str(tmp_path / "result")]) == expected
    content = (tmp_path / "result.agent.html").read_text(encoding="utf-8")
    assert "&lt;script&gt;" in content
    assert "<script>" not in content
    assert json.loads((tmp_path / "result.agent.json").read_text(encoding="utf-8"))["status"] == status
    assert json.loads(capsys.readouterr().out)["status"] == status


def test_cli_rejects_combining_agent_and_legacy_execution(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["--agent-task", str(tmp_path / "task.json"), "--execute_str", "[]"])
    assert error.value.code == 2


def test_mcp_agent_report_sets_is_error_and_structured_content():
    with patch("je_web_runner.mcp_server.agent_tools.run_agent", return_value=AgentReport(status="failed")):
        result = call_tool("webrunner_run_agent", {"task": task_json()})
    assert result["isError"] is True
    assert result["structuredContent"]["status"] == "failed"


def test_mcp_task_cannot_grant_itself_host_secret_access(monkeypatch):
    monkeypatch.delenv("WEBRUNNER_AGENT_ALLOWED_ENV", raising=False)
    task = {**task_json(), "allowed_env": ["PRIVATE_HOST_KEY"]}
    with patch("je_web_runner.mcp_server.agent_tools.run_agent") as execute:
        result = call_tool("webrunner_run_agent", {"task": task})
    assert result["isError"] is True
    assert "WEBRUNNER_AGENT_ALLOWED_ENV" in result["content"][0]["text"]
    execute.assert_not_called()


def test_mcp_budgets_are_capped_by_host():
    task = {**task_json(), "timeout": 999999, "action_timeout": 999999, "max_steps": 999999}
    with patch("je_web_runner.mcp_server.agent_tools.run_agent", return_value=AgentReport(status="success")) as run:
        result = call_tool("webrunner_run_agent", {"task": task})
    assert result["isError"] is False
    spec = run.call_args.args[0]
    assert (spec.timeout, spec.action_timeout, spec.max_steps) == (300, 15, 100)


def test_mcp_step_rejects_arbitrary_code_before_borrowing_browser():
    with patch("je_web_runner.mcp_server.agent_tools._borrow") as borrow:
        result = call_tool("webrunner_agent_step", {"action": {"kind": "execute_script", "value": "x"}})
    assert result["isError"] is True
    borrow.assert_not_called()


def test_html_report_is_standalone_and_escaped(tmp_path):
    report = AgentReport(stopped_reason='<img src="x" onerror="alert(1)">')
    paths = write_agent_report(report, tmp_path / "nested" / "run")
    assert len(paths) == 2
    assert "&lt;img" in (tmp_path / "nested" / "run.agent.html").read_text(encoding="utf-8")
