"""Host-owned, loopback-only browser acceptance contracts, independent of model suggestions."""
from __future__ import annotations

import re
import json
from typing import Any
from urllib.parse import urlsplit

from je_web_runner.utils.agent.types import AgentError, TaskSpec
from je_web_runner.utils.issue_worker.types import IssueWorkerError


def scenario_task(value: dict[str, Any]) -> TaskSpec:
    """Validate a fixed scenario with no cloud planner, environment secrets or external targets."""
    if not isinstance(value, dict) or set(value) != {"server", "port", "task"}:
        raise IssueWorkerError("browser scenario requires only server, port and task")
    command, port = value["server"], value["port"]
    if len(json.dumps(value)) > 64000:
        raise IssueWorkerError("browser scenario exceeds its size limit")
    if not isinstance(command, list) or not command or not all(isinstance(arg, str) and arg for arg in command):
        raise IssueWorkerError("browser server must be a host-owned argv list")
    if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
        raise IssueWorkerError("browser server port must be between 1024 and 65535")
    try:
        task = TaskSpec.from_dict(value["task"])
    except AgentError as error:
        raise IssueWorkerError("invalid browser acceptance task") from error
    _task_limits(task)
    urls = [task.start_url, *(action.value for action in task.steps if action.kind == "navigate")]
    for url in urls:
        target = urlsplit(url)
        if target.scheme != "http" or target.netloc != f"127.0.0.1:{port}":
            raise IssueWorkerError("browser acceptance URLs must use the configured container loopback port")
    return task


def _task_limits(task: TaskSpec) -> None:
    if task.planner != "steps" or task.allowed_env or not task.headless:
        raise IssueWorkerError("acceptance uses headless fixed steps without environment secrets")
    if task.max_steps > 100 or task.timeout > 120 or task.action_timeout > 15:
        raise IssueWorkerError("browser acceptance exceeds host task limits")
    if len(task.steps) > 100 or len(task.success) > 20:
        raise IssueWorkerError("browser acceptance exceeds step/assertion limits")


def validate_scenarios(scenarios: Any) -> None:
    """Accept at most ten named host scenarios; every configured scenario is mandatory."""
    if not isinstance(scenarios, dict) or len(scenarios) > 10:
        raise IssueWorkerError("browser_scenarios must contain at most ten named scenarios")
    for name, value in scenarios.items():
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", name):
            raise IssueWorkerError("invalid browser scenario name")
        scenario_task(value)
