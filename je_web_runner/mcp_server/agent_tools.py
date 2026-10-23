"""MCP tools for local browser observations, bounded actions and verified tasks."""
from __future__ import annotations

import os
from typing import Any

from je_web_runner.mcp_server._types import DRIVES_BROWSER, Tool, ToolResult
from je_web_runner.utils.agent import AgentAction, AgentError, TaskSpec, run_agent
from je_web_runner.utils.agent.browser import BrowserSession
from je_web_runner.utils.agent.runner import Redactor, agent_session, browser_privacy, execute_browser_action
from je_web_runner.utils.agent.planners import ACTION_SCHEMA
from je_web_runner.utils.agent.schema import build_agent_schema

_BACKEND = {"type": "string", "enum": ["selenium", "playwright"], "description": "Active browser backend."}
_MCP_REDACTOR = Redactor()


def _borrow(backend: str) -> BrowserSession:
    if backend == "playwright":
        from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
        driver = playwright_wrapper_instance.page
    else:
        from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance
        driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise AgentError("start a browser through webrunner_run_actions first")
    return BrowserSession(driver, backend)


def _allowed_env() -> list[str]:
    return [name.strip() for name in os.environ.get("WEBRUNNER_AGENT_ALLOWED_ENV", "").split(",") if name.strip()]


def _redactor() -> Redactor:
    redactor = _MCP_REDACTOR
    redactor.secrets.update(os.environ[name] for name in _allowed_env() if os.environ.get(name))
    return redactor


def _observe(arguments: dict[str, Any]) -> Any:
    with agent_session(), browser_privacy():
        browser = _borrow(arguments.get("backend", "selenium"))
        browser.set_timeout(15)
        return _redactor().clean(browser.observe())


def _step(arguments: dict[str, Any]) -> Any:
    action = AgentAction.from_dict(arguments["action"])
    with agent_session(), browser_privacy():
        browser = _borrow(arguments.get("backend", "selenium"))
        browser.set_timeout(15)
        redactor = _redactor()
        resolved = redactor.resolve(action, _allowed_env())
        result = execute_browser_action(browser, resolved, redactor)
        return redactor.clean({"result": result, "observation": browser.observe()})


def _run(arguments: dict[str, Any]) -> ToolResult:
    task = TaskSpec.from_dict(arguments["task"])
    if not set(task.allowed_env).issubset(_allowed_env()):
        raise AgentError("task allowed_env exceeds the host's WEBRUNNER_AGENT_ALLOWED_ENV")
    # A model caller cannot give itself an unbounded MCP request budget.
    task.max_steps = min(task.max_steps, 100)
    task.timeout = min(task.timeout, 300)
    task.action_timeout = min(task.action_timeout, 15)
    report = run_agent(task)
    return ToolResult(report.to_dict(), is_error=report.status != "success")


def build_agent_tools() -> list[Tool]:
    """Build the three local agent tools without changing legacy browser tool results."""
    definitions = [
        ("webrunner_observe_page", "Observe the active browser", _observe, {"backend": _BACKEND}, []),
        ("webrunner_agent_step", "Perform one validated browser agent action", _step,
         {"backend": _BACKEND, "action": {**ACTION_SCHEMA, "description": "Typed browser action; no code."}},
         ["action"]),
        ("webrunner_run_agent", "Run a verified task in its own local browser", _run,
         {"task": {**build_agent_schema(), "description": "TaskSpec with deterministic success conditions."}},
         ["task"]),
    ]
    tools = []
    for name, description, handler, properties, required in definitions:
        annotations = DRIVES_BROWSER if name != "webrunner_observe_page" else {
            "readOnlyHint": True, "openWorldHint": True,
        }
        tools.append(Tool(
            name=name, title=description, description=description,
            input_schema={"type": "object", "properties": properties, "required": required,
                          "additionalProperties": False},
            handler=handler, annotations=annotations,
        ))
    return tools
