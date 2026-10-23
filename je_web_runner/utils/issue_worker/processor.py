"""Checkpointed local coding loop with independent host validation."""
from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any, Callable

from je_web_runner.utils.agent.runner import Redactor, browser_privacy
from je_web_runner.utils.issue_worker.planner import CodeAction, CodingPlanner
from je_web_runner.utils.issue_worker.sandbox import PodmanSandbox
from je_web_runner.utils.issue_worker.types import IssueWorkerConfig, IssueWorkerError
from je_web_runner.utils.issue_worker.workspace import IssueWorkspace


class CodeProcessor:
    """Tool-limited coding, resumable checks and deterministic publication readiness."""

    def __init__(self, config: IssueWorkerConfig, planner: Any = None, sandbox: Any = None) -> None:
        self.config = config
        self.planner = planner or CodingPlanner(config.model, config.ollama_url, IssueWorkerError)
        self.sandbox = sandbox or PodmanSandbox(config)

    def close(self) -> None:
        """Close local inference connections."""
        self.planner.close()

    def preflight(self) -> None:
        """Check free local prerequisites before claiming a remote issue."""
        self.planner.preflight(15)
        self.sandbox.preflight()

    def process(self, job: dict[str, Any], workspace: IssueWorkspace,
                checkpoint: Callable[[str, dict[str, Any]], None], redactor: Redactor) -> str:
        """Return ready/failed/needs_info while checkpointing every significant side effect."""
        data = job["data"]
        data.setdefault("deadline", time.time() + self.config.timeout)
        data.setdefault("history", [])
        data.setdefault("tool_count", 0)
        data.setdefault("validation_rounds", 0)
        data.setdefault("checks", {})
        checkpoint("analyzing", data)
        with browser_privacy():
            if "baseline" not in data:
                name = "unit" if "unit" in self.config.checks else next(iter(self.config.checks))
                data["baseline"] = redactor.clean(self.sandbox.check(workspace, name, self._remaining(data)))
                checkpoint("analyzing", data)
            return self._loop(job, workspace, checkpoint, redactor)

    @staticmethod
    def _remaining(data: dict[str, Any]) -> float:
        remaining = data["deadline"] - time.time()
        if remaining <= 0:
            raise IssueWorkerError("issue exceeded its total time limit")
        return remaining

    def _loop(self, job: dict[str, Any], workspace: IssueWorkspace,
              checkpoint: Callable[[str, dict[str, Any]], None], redactor: Redactor) -> str:
        data = job["data"]
        if data.get("phase") == "validating":
            if self._validate(workspace, data, checkpoint, redactor):
                return "ready"
            if data["validation_rounds"] >= self.config.repair_rounds:
                return "failed"
        while data["tool_count"] < self.config.max_tools:
            self._remaining(data)
            context = self._context(job, workspace, redactor)
            action = self.planner.plan(context, min(120, self._remaining(data)))
            self._remaining(data)
            if not isinstance(action, CodeAction):
                raise IssueWorkerError("coding planner must return CodeAction")
            data["tool_count"] += 1
            checkpoint("fixing", data)
            if action.kind == "needs_info":
                data["reason"] = redactor.clean(action.summary)
                return "needs_info"
            if action.kind == "finish":
                data["summary"] = redactor.clean(action.summary[:2000])
                data["phase"] = "validating"
                checkpoint("validating", data)
                if self._validate(workspace, data, checkpoint, redactor):
                    return "ready"
                if data["validation_rounds"] >= self.config.repair_rounds:
                    return "failed"
            else:
                self._tool(action, workspace, data, checkpoint, redactor)
        data["reason"] = "issue exceeded its tool operation limit"
        return "failed"

    def _context(self, job: dict[str, Any], workspace: IssueWorkspace, redactor: Redactor) -> dict[str, Any]:
        instructions = {}
        for name in ("CLAUDE.md", "architecture.md", "pyproject.toml"):
            if (workspace.root / name).is_file():
                instructions[name] = workspace.read(name)[:8000]
        return redactor.clean({
            "issue": job["snapshot"], "repository_instructions": instructions,
            "files": workspace.files()[:500], "check_names": list(self.config.checks),
            "history": job["data"]["history"][-12:], "checks": job["data"]["checks"],
            "baseline": job["data"]["baseline"],
        })

    def _tool(self, action: CodeAction, workspace: IssueWorkspace, data: dict[str, Any],
              checkpoint: Callable[[str, dict[str, Any]], None], redactor: Redactor) -> None:
        handlers = {"read": lambda: workspace.read(action.path), "search": lambda: workspace.search(action.text),
                    "patch": lambda: workspace.patch(action.text),
                    "check": lambda: self.sandbox.check(workspace, action.check, self._remaining(data))}
        entry: dict[str, Any]
        try:
            result = handlers[action.kind]()
            if action.kind == "patch":
                data["checks"] = {}
            if action.kind == "check":
                data["checks"][action.check] = redactor.clean(result)
            entry = {"action": asdict(action), "result": result}
        except IssueWorkerError as error:
            entry = {"action": asdict(action), "error": str(error)}
        if action.kind == "patch":
            entry["action"]["text"] = "<patch stored in isolated git index>"
        rendered = redactor.clean(entry)
        if isinstance(rendered.get("result"), str):
            rendered["result"] = rendered["result"][:16000]
        data["history"].append(rendered)
        data["history"] = data["history"][-12:]
        checkpoint("fixing", data)

    def _validate(self, workspace: IssueWorkspace, data: dict[str, Any],
                  checkpoint: Callable[[str, dict[str, Any]], None], redactor: Redactor) -> bool:
        workspace.verify_scope()
        changes = workspace.changes()
        if not changes:
            data["reason"] = "no code or documentation changes were produced"
            data["validation_rounds"] += 1
            data["phase"] = "fixing"
            checkpoint("fixing", data)
            return False
        tree = workspace.fingerprint()
        checkpoint("validating", data)
        for name in self.config.checks:
            previous = data["checks"].get(name, {})
            if previous.get("tree") != tree or not previous.get("passed"):
                data["checks"][name] = redactor.clean(self.sandbox.check(workspace, name, self._remaining(data)))
                checkpoint("validating", data)
        self._remaining(data)
        passed = all(data["checks"][name].get("passed") and data["checks"][name].get("tree") == tree
                     for name in self.config.checks)
        if passed:
            data["validated_tree"] = tree
            data["phase"] = "ready"
        else:
            data["validation_rounds"] += 1
            data["reason"] = "required host validation checks failed"
            data["history"].append({"validation_failed": data["checks"]})
            data["phase"] = "fixing"
            checkpoint("fixing", data)
        return passed
