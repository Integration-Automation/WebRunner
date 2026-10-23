"""Offline Podman validation with no source credentials or container socket mounts."""
from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from je_web_runner.utils.issue_worker.types import IssueWorkerConfig, IssueWorkerError
from je_web_runner.utils.issue_worker.workspace import IssueWorkspace


def transport_environment() -> dict[str, str]:
    """Only OS/container connection settings go to Podman; API credentials do not."""
    names = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT", "USERPROFILE", "HOME",
             "APPDATA", "LOCALAPPDATA", "XDG_RUNTIME_DIR"}
    return {name: value for name, value in os.environ.items() if name.upper() in names}


class PodmanSandbox:
    """Run only host-owned named checks in a prebuilt local image."""

    def __init__(self, config: IssueWorkerConfig) -> None:
        self.config = config
        self.executable = shutil.which("podman") or "podman"

    def preflight(self) -> None:
        """Fail closed if Podman or the explicitly installed image is unavailable."""
        try:
            result = subprocess.run(  # nosec B603
                [self.executable, "image", "inspect", self.config.image], capture_output=True,
                env=transport_environment(), timeout=30, check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise IssueWorkerError("Podman and its local worker image must be installed first") from error
        if result.returncode:
            raise IssueWorkerError("local Podman worker image is unavailable; runtime never pulls images")

    def argv(self, workspace: IssueWorkspace, check: str, source: Path, name: str) -> list[str]:
        """Construct fixed sandbox policy around a configured check argv."""
        if check not in self.config.checks:
            raise IssueWorkerError("model requested an unknown host check")
        changed = [path for _a, _d, path in workspace.changes()
                   if path.endswith(".py") and (workspace.root / path).exists()]
        command = []
        for argument in self.config.checks[check]:
            command.extend(changed if argument == "{changed_python}" else [argument])
        if "{changed_python}" in self.config.checks[check] and not changed:
            return []
        return [
            self.executable, "run", "--rm", "--name", name, "--pull=never", "--network=none", "--read-only",
            "--user", "65532:65532", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            # A private per-container tmpfs, not a shared host temporary directory.
            "--pids-limit=256", "--memory=4g", "--cpus=2", "--tmpfs", "/tmp:rw,nosuid,nodev,size=1g",  # nosec B108
            "--mount", f"type=bind,src={source},destination=/work,ro=true", "--workdir", "/work",
            "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "PYTHONPATH=/work", "--env", "HOME=/tmp",
            "--env", "WEBRUNNER_LOG_PATH=/tmp/webrunner.log", "--env", "SE_OFFLINE=true",
            self.config.image, *command,
        ]

    def check(self, workspace: IssueWorkspace, name: str, timeout: float) -> dict[str, Any]:
        """Export a disposable read-only source snapshot; cap time and output size."""
        workspace.verify_scope()
        tree = workspace.fingerprint()
        with tempfile.TemporaryDirectory(prefix="webrunner-issue-check-") as temporary:
            source = Path(temporary) / "source"
            workspace.export(source)
            container = "webrunner-issue-" + secrets.token_hex(12)
            argv = self.argv(workspace, name, source, container)
            if not argv:
                return {"name": name, "passed": True, "tree": tree, "output": "No changed Python files."}
            result = self._execute(argv, container, Path(temporary) / "output.log", timeout)
            return {"name": name, "tree": tree, **result}

    def _execute(self, argv: list[str], container: str, output: Path, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        reason = ""
        with output.open("wb") as stream:
            process = subprocess.Popen(  # nosec B603
                argv, stdout=stream, stderr=subprocess.STDOUT, env=transport_environment(),
            )
            try:
                while process.poll() is None:
                    if time.monotonic() >= deadline or output.stat().st_size > 2_000_000:
                        reason = "check exceeded its time or output limit"
                        process.kill()
                        process.wait(timeout=5)
                        break
                    threading.Event().wait(0.1)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                self._remove_container(container)
        with output.open("rb") as stream:
            stream.seek(max(0, output.stat().st_size - 20000))
            text = stream.read().decode("utf-8", errors="replace")
        return {"passed": process.returncode == 0 and not reason, "output": text, "reason": reason}

    def _remove_container(self, name: str) -> None:
        result = subprocess.run(  # nosec B603
            [self.executable, "rm", "--force", "--ignore", name], env=transport_environment(),
            capture_output=True, timeout=15, check=False,
        )
        if result.returncode:
            raise IssueWorkerError("could not remove the isolated check container")
