"""Validated task, action and report interfaces for local browser agents."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import urlsplit

from je_web_runner.utils.exception.exceptions import WebRunnerException


class AgentError(WebRunnerException):
    """A task, planner response or agent operation is invalid."""


def http_url(value: str) -> str:
    """Accept absolute HTTP(S) URLs without embedded credentials."""
    if not isinstance(value, str):
        raise AgentError("URL must be a string")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise AgentError("URL must be absolute HTTP(S) without credentials")
    return value


def positive(value: Any, name: str) -> None:
    """Require finite, positive limits; booleans are not numbers here."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise AgentError(f"{name} must be finite and positive")


def text(value: Any, name: str) -> None:
    """Require a nonempty string."""
    if not isinstance(value, str) or not value.strip():
        raise AgentError(f"{name} must be a nonempty string")


@dataclass(frozen=True)
class AgentAction:
    """A single supported browser operation; selectors are CSS, never source code."""

    kind: str
    selector: str = ""
    value: str = ""
    key: str = ""
    frame: str = ""

    def __post_init__(self) -> None:
        kinds = {"navigate", "click", "fill", "select", "check", "scroll", "wait", "extract", "done"}
        if not isinstance(self.kind, str) or self.kind not in kinds:
            raise AgentError("unsupported agent action")
        if not all(isinstance(value, str) for value in (self.selector, self.value, self.key, self.frame)):
            raise AgentError("action fields must be strings")
        if self.kind in {"click", "fill", "select", "check", "wait", "extract"}:
            text(self.selector, "selector")
        if self.kind == "navigate":
            http_url(self.value)
        if self.kind == "extract":
            text(self.key, "extract key")

    @classmethod
    def from_dict(cls, value: Any) -> AgentAction:
        """Parse a closed action object without echoing sensitive input in errors."""
        if not isinstance(value, dict):
            raise AgentError("action must be an object")
        try:
            return cls(**value)
        except TypeError as error:
            raise AgentError("action has missing or unknown fields") from error


@dataclass(frozen=True)
class SuccessCondition:
    """A deterministic URL, visible element, text or extracted-value assertion."""

    kind: str
    value: str = ""
    selector: str = ""
    key: str = ""
    frame: str = ""

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) for value in (self.kind, self.value, self.selector, self.key, self.frame)):
            raise AgentError("condition fields must be strings")
        if self.kind not in {"url_contains", "text_contains", "visible", "extracted_equals"}:
            raise AgentError("unsupported success condition")
        if self.kind in {"url_contains", "text_contains"}:
            text(self.value, "condition value")
        if self.kind == "visible":
            text(self.selector, "condition selector")
        if self.kind == "extracted_equals":
            text(self.key, "condition key")


@dataclass
class TaskSpec:
    """One local task. All success conditions must pass; steps need no model."""

    goal: str
    start_url: str
    success: list[SuccessCondition]
    backend: str = "selenium"
    planner: str = "steps"
    model: str = ""
    steps: list[AgentAction] = field(default_factory=list)
    extract: dict[str, str] = field(default_factory=dict)
    max_steps: int = 25
    timeout: float = 300.0
    action_timeout: float = 15.0
    headless: bool = True
    allowed_env: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        text(self.goal, "goal")
        http_url(self.start_url)
        self._validate_execution()
        self._validate_collections()
        self._validate_limits()

    def _validate_execution(self) -> None:
        if self.backend not in {"selenium", "playwright"} or self.planner not in {"steps", "ollama"}:
            raise AgentError("backend must be selenium/playwright; planner must be steps/ollama")
        if self.planner == "ollama":
            text(self.model, "local model name")
        if not isinstance(self.headless, bool):
            raise AgentError("headless must be a boolean")

    def _validate_collections(self) -> None:
        if not isinstance(self.success, list) or not self.success:
            raise AgentError("at least one success condition is required")
        if not all(isinstance(item, SuccessCondition) for item in self.success):
            raise AgentError("success must contain SuccessCondition objects")
        if not isinstance(self.steps, list) or not all(isinstance(item, AgentAction) for item in self.steps):
            raise AgentError("steps must contain AgentAction objects")
        self._validate_fields()

    def _validate_limits(self) -> None:
        if not isinstance(self.max_steps, int) or isinstance(self.max_steps, bool):
            raise AgentError("max_steps must be an integer")
        for name in ("max_steps", "timeout", "action_timeout"):
            positive(getattr(self, name), name)

    def _validate_fields(self) -> None:
        if not isinstance(self.allowed_env, list) or not all(
            isinstance(name, str) and name.isidentifier() for name in self.allowed_env
        ):
            raise AgentError("allowed_env must contain environment variable names")
        if not isinstance(self.extract, dict):
            raise AgentError("extract must map field names to CSS selectors")
        for key, selector in self.extract.items():
            text(key, "extract key")
            text(selector, "extract selector")

    @classmethod
    def from_dict(cls, value: Any) -> TaskSpec:
        """Parse task JSON and reject unknown fields before opening a browser."""
        if not isinstance(value, dict):
            raise AgentError("task must be an object")
        data = dict(value)
        try:
            data["steps"] = [AgentAction.from_dict(item) for item in data.get("steps", [])]
            data["success"] = [SuccessCondition(**item) for item in data.get("success", [])]
            return cls(**data)
        except (TypeError, KeyError) as error:
            raise AgentError("task has missing, unknown or incorrectly typed fields") from error


@dataclass
class AgentReport:
    """Serializable agent outcome; success always means deterministic verification passed."""

    status: str = "failed"
    stopped_reason: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    extracted: dict[str, str] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return plain JSON-compatible data."""
        return asdict(self)
