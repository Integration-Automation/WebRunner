"""Bounded local readiness diagnostics and explicitly requested read-only platform checks."""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from je_web_runner.utils.ai_assist.local_client import LocalOllamaClient
from je_web_runner.utils.issue_worker.providers import GitHubIssues, JiraIssues, MANAGED
from je_web_runner.utils.issue_worker.sandbox import PodmanSandbox, transport_environment
from je_web_runner.utils.issue_worker.types import IssueWorkerConfig, IssueWorkerError


class IssueDoctor:
    """Inspect readiness without claiming issues, pulling images or generating model output."""

    def __init__(self, config: IssueWorkerConfig) -> None:
        self.config = config

    def check(self, include_platform: bool = False) -> dict[str, Any]:
        """Return stable diagnostic codes; errors deliberately omit subprocess/HTTP bodies."""
        checks = [
            self._probe("git", self._git, "Install Git and add it to this user's PATH."),
            self._probe("state", self._state, "Check state directory access, disk space and SQLite health."),
            self._probe("podman", PodmanSandbox(self.config).preflight,
                        "Start Podman and prepare the configured image; diagnostics never pull it."),
            self._probe("ollama", self._ollama,
                        "Start local Ollama with OLLAMA_NO_CLOUD=1 and install the configured model."),
        ]
        if include_platform:
            checks.append(self._probe("github", self._github,
                                      "Check token identity, repository/dev access and all automation labels."))
            if self.config.jira_url:
                checks.append(self._probe("jira", self._jira,
                                          "Check Jira identity and access to every allowed project."))
            checks.append({"name": "write_permissions", "status": "unverified", "required": False,
                           "code": "write_permissions_unverified",
                           "hint": "Read-only checks cannot prove every effective platform write permission."})
        return {"ready": all(item["status"] != "failed" for item in checks), "checks": checks}

    @staticmethod
    def _probe(name: str, operation: Callable[[], Any], hint: str) -> dict[str, Any]:
        try:
            operation()
        except Exception:  # Report a bounded code, never raw errors containing host secrets.
            return {"name": name, "status": "failed", "required": True, "code": name + "_unavailable",
                    "hint": hint}
        return {"name": name, "status": "passed", "required": True, "code": name + "_ready", "hint": ""}

    @staticmethod
    def _git() -> None:
        executable = shutil.which("git")
        if not executable:
            raise IssueWorkerError("Git is unavailable")
        result = subprocess.run([executable, "--version"], capture_output=True, timeout=10,  # nosec B603
                                env=transport_environment(), check=False)
        if result.returncode:
            raise IssueWorkerError("Git is unavailable")

    def _state(self) -> None:
        root = Path(self.config.state_dir).resolve()
        root.mkdir(parents=True, exist_ok=True)
        if not shutil.disk_usage(root).free:
            raise IssueWorkerError("state disk has no free space")
        with tempfile.TemporaryDirectory(prefix="doctor-", dir=root) as temporary:
            connection = sqlite3.connect(str(Path(temporary) / "probe.sqlite3"))
            try:
                connection.execute("CREATE TABLE probe (value INTEGER)")
                connection.execute("INSERT INTO probe VALUES (1)")
                connection.commit()
            finally:
                connection.close()
        database = root / "issues.sqlite3"
        if database.exists():
            connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)
            try:
                rows = connection.execute("PRAGMA quick_check").fetchall()
                if rows != [("ok",)]:
                    raise IssueWorkerError("state database failed its integrity check")
            finally:
                connection.close()

    def _ollama(self) -> None:
        client = LocalOllamaClient(self.config.model, self.config.ollama_url, IssueWorkerError)
        try:
            client.preflight(15)
        finally:
            client.close()

    def _github(self) -> None:
        provider = GitHubIssues(self.config)
        try:
            provider.authorize()
            provider.client.request("GET", provider.prefix)
            provider.client.request("GET", provider.prefix + "/git/ref/heads/" + self.config.base_branch)
            for name in sorted(MANAGED | {"automation-ready"}):
                provider.client.request("GET", provider.prefix + "/labels/" + quote(name, safe=""))
        finally:
            provider.close()

    def _jira(self) -> None:
        provider = JiraIssues(self.config)
        try:
            provider.authorize()
            for project in self.config.jira_projects:
                provider.client.request("GET", "/rest/api/3/project/" + quote(project, safe=""))
        finally:
            provider.close()
