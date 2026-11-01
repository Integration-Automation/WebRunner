"""Bounded observe/plan/execute/verify loop using the existing action executor."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Iterator

from je_web_runner.utils.agent.browser import BrowserSession
from je_web_runner.utils.agent.planners import OllamaPlanner, StepsPlanner
from je_web_runner.utils.agent.types import AgentAction, AgentError, AgentReport, TaskSpec
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.smart_wait.smart_wait import SmartWaitError, wait_until

_SESSION_LOCK = threading.Lock()
_ENV = re.compile(r"\$\{ENV\.([A-Za-z_][A-Za-z0-9_]*)\}")


@contextmanager
def browser_privacy() -> Iterator[None]:
    """Keep raw driver request/response bodies out of host debug handlers on this thread."""
    active_thread = threading.get_ident()

    def privacy_filter(record: logging.LogRecord) -> bool:
        return record.thread != active_thread
    loggers = [logging.getLogger(name) for name in (
        "selenium.webdriver.remote.remote_connection", "urllib3.connectionpool",
    )]
    for logger in loggers:
        logger.addFilter(privacy_filter)
    try:
        yield
    finally:
        for logger in loggers:
            logger.removeFilter(privacy_filter)


@contextmanager
def agent_session() -> Iterator[None]:
    """Refuse concurrent agent operations in one process instead of sharing browser state."""
    if not _SESSION_LOCK.acquire(blocking=False):
        raise AgentError("another agent operation is active; use separate processes for parallel tasks")
    try:
        yield
    finally:
        _SESSION_LOCK.release()


class Redactor:
    """Redact explicit environment secrets, entered values and common credential patterns."""

    def __init__(self) -> None:
        self.secrets: set[str] = set()

    def clean(self, value: Any) -> Any:
        """Return sanitized JSON-compatible data without mutating its source."""
        if isinstance(value, dict):
            return {key: self.clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.clean(item) for item in value]
        if not isinstance(value, str):
            return value
        for secret in sorted(self.secrets, key=len, reverse=True):
            if secret:
                value = value.replace(secret, "<hidden>")
        value = re.sub(r"(?i)(bearer\s+)[\w.-]+", r"\1<hidden>", value)
        return re.sub(r"(?i)([?&](?:token|api_key|password|secret|access_key)=)[^&\s]*", r"\1<hidden>", value)

    def resolve(self, action: AgentAction, allowed_env: list[str]) -> AgentAction:
        """Resolve only explicitly allowed environment placeholders, immediately before execution."""
        def substitute(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in allowed_env or name not in os.environ:
                raise AgentError("environment placeholder is not allowed or is unset")
            value = os.environ[name]
            if value:
                self.secrets.add(value)
            return value

        value = _ENV.sub(substitute, action.value)
        if action.kind == "fill" and value:
            self.secrets.add(value)
        return replace(action, value=value)


def execute_browser_action(browser: Any, action: AgentAction, redactor: Redactor, executor: Any = None) -> Any:
    """Execute a validated operation through a quiet, non-retrying executor command."""
    from je_web_runner.utils.executor.action_executor import Executor
    command_executor = executor if executor is not None else Executor()

    def perform() -> Any:
        try:
            return browser.perform(action)
        except Exception as error:
            raise AgentError(redactor.clean(f"{type(error).__name__}: {error}")) from None

    command_executor.event_dict["WR_agent_step"] = perform
    return command_executor.execute_one(["WR_agent_step"])


class AgentRunner:
    """One task runner; injected browsers remain owned by their caller."""

    def __init__(self, task: TaskSpec, browser: Any = None, planner: Any = None,
                 artifact_dir: str | Path | None = None) -> None:
        task.__post_init__()
        self.task = task
        self.browser = browser
        self.planner = planner
        self.artifact_dir = Path(artifact_dir) if artifact_dir is not None else None
        self.redactor = Redactor()
        self.redactor.secrets.update(os.environ[name] for name in task.allowed_env if os.environ.get(name))
        self.report = AgentReport()
        self.deadline = 0.0
        self._executor: Any = None
        self._started = False

    def remaining(self) -> float:
        """The remaining wall-clock budget; expired runs cannot report success."""
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("agent task exceeded its total time limit")
        return remaining

    def run(self) -> AgentReport:
        """Run to verified success, bounded stop or failure, cleaning up owned resources."""
        with agent_session(), browser_privacy():
            if self._started:
                raise AgentError("this AgentRunner already ran; create a new runner for another task")
            self._started = True
            return self._run_owned()

    def _run_owned(self) -> AgentReport:
        owns_browser = self.browser is None
        owns_planner = self.planner is None
        self.deadline = time.monotonic() + self.task.timeout
        self.report = AgentReport()
        try:
            self._setup()
            self._loop()
        except TimeoutError:
            self.report.status = "timeout"
            self.report.stopped_reason = "agent task exceeded its total time limit"
        except Exception as error:
            self.report.stopped_reason = self.redactor.clean(f"{type(error).__name__}: {error}")
            web_runner_logger.warning("agent task failed: %s", self.report.stopped_reason)
        finally:
            self._failure_screenshot()
            if owns_browser and self.browser is not None:
                self._cleanup(self.browser)
            if owns_planner and self.planner is not None and hasattr(self.planner, "close"):
                self._cleanup(self.planner)
        sanitized = self.redactor.clean(self.report.to_dict())
        self.report = AgentReport(**sanitized)
        return self.report

    def _cleanup(self, resource: Any) -> None:
        try:
            resource.close()
        except Exception as error:
            web_runner_logger.warning("agent resource cleanup failed: %s", type(error).__name__)

    def _setup(self) -> None:
        from je_web_runner.utils.executor.action_executor import Executor
        if self.planner is None:
            self.planner = OllamaPlanner(self.task) if self.task.planner == "ollama" else StepsPlanner(self.task)
        if hasattr(self.planner, "preflight"):
            self.planner.preflight(min(10, self.remaining()))
        if self.browser is None:
            self.browser = BrowserSession.open(self.task.backend, self.task.headless)
        self.browser.set_timeout(min(self.task.action_timeout, self.remaining()))
        self._executor = Executor()
        # No model action or secret appears in an executor record. The command invokes
        # only the already validated operation; its retry policy stays at zero.
        execute_browser_action(self.browser, AgentAction("navigate", value=self.task.start_url),
                               self.redactor, self._executor)

    def _loop(self) -> None:
        previous = ""
        repeats = 0
        for step in range(self.task.max_steps):
            self.remaining()
            if self._verified():
                return
            self.browser.set_timeout(min(self.task.action_timeout, self.remaining()))
            observation = self.redactor.clean(self.browser.observe(step))
            observation["recent_steps"] = self.redactor.clean(self.report.steps[-5:])
            observation["extracted"] = self.redactor.clean(self.report.extracted)
            action = self.planner.plan(observation, min(60, self.remaining()))
            self.remaining()
            if not isinstance(action, AgentAction):
                raise AgentError("planner must return AgentAction")
            if action.kind == "done":
                self._wait_for_success()
                return
            signature = self._fingerprint(observation, action)
            repeats = repeats + 1 if signature == previous else 1
            previous = signature
            if repeats >= 3:
                self.report.stopped_reason = "same action and page state proposed three consecutive times"
                return
            self._step(action, observation)
        if not self._verified():
            self.report.stopped_reason = f"reached max_steps={self.task.max_steps}"

    @staticmethod
    def _fingerprint(observation: dict[str, Any], action: AgentAction) -> str:
        state = {key: observation.get(key) for key in ("url", "title", "text", "elements", "frames")}
        payload = json.dumps([state, asdict(action)], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _step(self, action: AgentAction, observation: dict[str, Any]) -> None:
        resolved = self.redactor.resolve(action, self.task.allowed_env)
        rendered = asdict(action)
        if action.kind == "fill":
            rendered["value"] = "<hidden>"
        entry = {"action": self.redactor.clean(rendered), "url": observation.get("url"), "status": "failed"}
        self.report.steps.append(entry)
        self.browser.set_timeout(min(self.task.action_timeout, self.remaining()))
        result = execute_browser_action(self.browser, resolved, self.redactor, self._executor)
        if action.kind == "extract":
            self.report.extracted[action.key] = result or ""
        entry["status"] = "passed"
        self.remaining()

    def _verified(self) -> bool:
        self.remaining()
        self.browser.set_timeout(min(self.task.action_timeout, self.remaining()))
        try:
            for key, selector in self.task.extract.items():
                self.report.extracted[key] = self.browser.text(selector)
            passed = all(self._condition(item) for item in self.task.success)
        except AgentError:
            return False
        self.remaining()
        if passed:
            self.report.status = "success"
            self.report.stopped_reason = "all success conditions passed"
        return passed

    def _condition(self, condition: Any) -> bool:
        if condition.kind == "url_contains":
            return condition.value in self.browser.url
        if condition.kind == "visible":
            return self.browser.visible(condition.selector, condition.frame)
        if condition.kind == "text_contains":
            return condition.value in self.browser.text(condition.selector or "body", condition.frame)
        return self.report.extracted.get(condition.key) == condition.value

    def _wait_for_success(self) -> None:
        try:
            wait_until(self._verified, timeout=min(self.task.action_timeout, self.remaining()),
                       poll=0.05, description="agent success conditions")
        except SmartWaitError:
            self.remaining()
            self.report.stopped_reason = "planner finished before success conditions passed"

    def _failure_screenshot(self) -> None:
        if self.report.status == "success" or self.browser is None or self.artifact_dir is None:
            return
        try:
            self.artifact_dir.mkdir(parents=True, exist_ok=True)
            target = self.artifact_dir / "failure.png"
            self.browser.screenshot(target, self.redactor.secrets)
            self.report.artifacts.append(str(target.resolve()))
        except Exception as error:
            web_runner_logger.warning("agent failure screenshot unavailable: %s", type(error).__name__)


def run_agent(task: TaskSpec | dict[str, Any], *, artifact_dir: str | Path | None = None) -> AgentReport:
    """Run a task with a local browser and optional local model; never use cloud inference."""
    specification = TaskSpec.from_dict(task) if isinstance(task, dict) else task
    if not isinstance(specification, TaskSpec):
        raise AgentError("task must be a TaskSpec or task object")
    return AgentRunner(specification, artifact_dir=artifact_dir).run()
