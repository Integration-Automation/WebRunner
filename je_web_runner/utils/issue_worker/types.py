"""Host-owned configuration and durable issue worker contracts."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from je_web_runner.utils.exception.exceptions import WebRunnerException

REPOSITORY = "Integration-Automation/WebRunner"
ACTIVE = {"claimed", "analyzing", "fixing", "validating", "publishing"}
FINAL = {"awaiting_review", "needs_info", "failed", "cancelled"}
CHECKS = {
    "unit": ["python", "-m", "pytest", "test/unit_test", "-q", "-p", "no:cacheprovider"],
    "lint": ["python", "-m", "flake8", "{changed_python}", "--max-line-length=120", "--max-complexity=10"],
    "security": ["python", "-m", "bandit", "{changed_python}", "-ll", "-q"],
    "types": ["python", "-m", "mypy", "{changed_python}", "--follow-imports=silent", "--ignore-missing-imports",
              "--cache-dir=/tmp/mypy-cache"],
}


class IssueWorkerError(WebRunnerException):
    """Invalid configuration or a bounded worker operation failed."""


class EnvironmentUnavailable(IssueWorkerError):
    """Shared local dependencies are unavailable; keep the job resumable."""


class ProviderError(IssueWorkerError):
    """A platform request failed without exposing its credentials or response body."""

    def __init__(self, message: str, retry_after: float = 0, permanent: bool = False) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.permanent = permanent


def api_url(value: str) -> str:
    """Require HTTPS except literal loopback HTTP used by local test fixtures."""
    parsed = urlsplit(value)
    local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise IssueWorkerError("invalid platform API URL")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise IssueWorkerError("platform APIs require HTTPS or loopback HTTP")
    return value.rstrip("/")


@dataclass(frozen=True)
class IssueSnapshot:
    """Normalized issue requirements; progress labels do not change the revision."""

    source: str
    external_id: str
    title: str
    body: str
    url: str
    labels: tuple[str, ...] = ()
    assignee: str = ""
    closed: bool = False
    kind: str = "development"

    def __post_init__(self) -> None:
        pattern = r"[1-9][0-9]*" if self.source == "github" else r"[A-Z][A-Z0-9_]*-[1-9][0-9]*"
        if self.source not in {"github", "jira"} or not re.fullmatch(pattern, self.external_id):
            raise IssueWorkerError("invalid issue source or identifier")

    @property
    def key(self) -> str:
        """Stable queue identity, scoped to the single configured repository/site."""
        return f"{self.source}:{self.external_id}"

    @property
    def revision(self) -> str:
        """Hash only human requirements, excluding bot progress and ownership."""
        payload = json.dumps([self.title, self.body, self.kind], ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def eligible(self, bot: str, resume: bool = False) -> bool:
        """Only ready, open and unassigned issues (or our own resumed claim) qualify."""
        owner_ok = not self.assignee or (resume and self.assignee == bot)
        return not self.closed and "automation-ready" in self.labels and owner_ok

    def to_dict(self) -> dict[str, Any]:
        """Return a portable snapshot."""
        return asdict(self)


@dataclass
class IssueWorkerConfig:
    """Trusted host settings; issue text and MCP callers cannot override these fields."""

    state_dir: str
    model: str
    github_bot: str
    repository: str = REPOSITORY
    base_branch: str = "dev"
    github_api: str = "https://api.github.com"
    github_token_env: str = "GITHUB_TOKEN"
    jira_url: str = ""
    jira_projects: list[str] = field(default_factory=list)
    jira_bot: str = ""
    jira_email_env: str = "JIRA_EMAIL"
    jira_token_env: str = "JIRA_API_TOKEN"
    ollama_url: str = "http://127.0.0.1:11434"
    image: str = "localhost/webrunner-issue-worker:local"
    poll_seconds: float = 60
    timeout: float = 3600
    max_tools: int = 100
    repair_rounds: int = 2
    max_files: int = 20
    max_lines: int = 1000
    review_enabled: bool = False
    max_review_rounds: int = 3
    review_poll_seconds: float = 60
    requirements_enabled: bool = False
    browser_scenarios: dict[str, dict[str, Any]] = field(default_factory=dict)
    checks: dict[str, list[str]] = field(default_factory=lambda: {key: list(value) for key, value in CHECKS.items()})

    def __post_init__(self) -> None:
        self._validate_identity()
        self._validate_limits()
        self._validate_checks()
        if not isinstance(self.requirements_enabled, bool):
            raise IssueWorkerError("requirements_enabled must be a boolean")
        from je_web_runner.utils.issue_worker.browser_contract import validate_scenarios
        validate_scenarios(self.browser_scenarios)

    def _validate_identity(self) -> None:
        for value in (self.state_dir, self.model, self.github_bot, self.image):
            if not isinstance(value, str) or not value.strip():
                raise IssueWorkerError("state_dir, model, github_bot and image are required")
        if self.repository != REPOSITORY or self.base_branch != "dev":
            raise IssueWorkerError("this worker targets Integration-Automation/WebRunner and dev only")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/@:+-]*", self.image):
            raise IssueWorkerError("image must be a container image name, not command flags")
        api_url(self.github_api)
        if self.jira_url:
            api_url(self.jira_url)
            if not self.jira_projects or not self.jira_bot:
                raise IssueWorkerError("Jira requires an explicit project allowlist and bot accountId")
        elif self.jira_projects or self.jira_bot:
            raise IssueWorkerError("Jira projects and bot require jira_url")
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        if not all(isinstance(name, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", name) for name in self.jira_projects):
            raise IssueWorkerError("invalid Jira project key")
        for name in (self.github_token_env, self.jira_email_env, self.jira_token_env):
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                raise IssueWorkerError("credentials must reference environment variable names")

    def _validate_limits(self) -> None:
        if not isinstance(self.review_enabled, bool):
            raise IssueWorkerError("review_enabled must be a boolean")
        for name in ("poll_seconds", "timeout", "max_tools", "repair_rounds", "max_files", "max_lines",
                     "max_review_rounds", "review_poll_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise IssueWorkerError(f"{name} must be finite and positive")
        for name in ("max_tools", "repair_rounds", "max_files", "max_lines", "max_review_rounds"):
            if not isinstance(getattr(self, name), int):
                raise IssueWorkerError(f"{name} must be an integer")

    def _validate_checks(self) -> None:
        if not isinstance(self.checks, dict) or not self.checks:
            raise IssueWorkerError("at least one host-owned validation command is required")
        for name, argv in self.checks.items():
            if not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
                raise IssueWorkerError("invalid validation command name")
            if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and arg for arg in argv):
                raise IssueWorkerError("validation commands must be nonempty argv lists")

    @classmethod
    def load(cls, path: str | Path) -> IssueWorkerConfig:
        """Load a closed host config, resolving state relative to the config file."""
        source = Path(path).resolve()
        try:
            config = cls(**json.loads(source.read_text(encoding="utf-8")))
        except (TypeError, ValueError) as error:
            raise IssueWorkerError("invalid issue worker configuration") from error
        config.state_dir = str((source.parent / config.state_dir).resolve())
        return config
