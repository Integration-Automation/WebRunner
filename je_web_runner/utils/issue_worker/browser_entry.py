"""Trusted container entry point: run a host scenario against an isolated application server."""
from __future__ import annotations

import json
import ctypes
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any

from je_web_runner.utils.agent.runner import AgentRunner
from je_web_runner.utils.issue_worker.browser_contract import scenario_task

RESULT_MARKER = "WEBRUNNER_BROWSER_RESULT="


def execute_case(case: dict[str, Any], workdir: Path) -> dict[str, Any]:
    """Run fixed browser steps and deterministic assertions; only host config supplies server argv."""
    task = scenario_task(case)
    deadline = time.monotonic() + task.timeout
    environment = {name: os.environ[name] for name in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP")
                   if name in os.environ}
    temporary = tempfile.gettempdir()
    environment.update({"PYTHONPATH": str(workdir), "PYTHONDONTWRITEBYTECODE": "1", "HOME": temporary,
                        "WEBRUNNER_LOG_PATH": str(Path(temporary) / "webrunner-app.log"), "SE_OFFLINE": "true"})
    process = subprocess.Popen(  # nosec B603
        case["server"], cwd=workdir, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        _wait_server(process, case["port"], min(deadline, time.monotonic() + 15))
        task.timeout = max(0.001, deadline - time.monotonic())
        runner = AgentRunner(task)
        report = runner.run().to_dict()
        report["conditions"] = runner.redactor.clean([
            {"kind": condition.kind, "selector": condition.selector[:200]} for condition in task.success])
        if time.monotonic() > deadline:
            report["status"] = "timeout"
        return report
    finally:
        _stop_server(process)


def _wait_server(process: subprocess.Popen, port: int, deadline: float) -> None:
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("acceptance server exited before readiness")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            threading.Event().wait(0.05)
    raise TimeoutError("acceptance server did not become ready")


def _stop_server(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main(path: str) -> int:
    """The manifest and this code are mounted read-only from the trusted host, outside the worktree."""
    try:
        _protect_verifier()
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
        full_report = execute_case(manifest["case"], Path("/work"))
        report = {"status": full_report["status"], "stopped_reason": full_report["stopped_reason"][:1000],
                  "steps_executed": len(full_report["steps"]),
                  "conditions_verified": len(manifest["case"]["task"]["success"])
                  if full_report["status"] == "success" else 0, "conditions": full_report.get("conditions", [])}
        report.update({"tree": manifest["tree"], "signature": manifest["signature"]})
    except Exception as error:
        report = {"status": "failed", "stopped_reason": type(error).__name__}
    print(RESULT_MARKER + json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "success" else 1


def _protect_verifier() -> None:
    """Deny the application child ptrace/proc access to verifier memory and inherited output handles."""
    if not sys.platform.startswith("linux"):
        raise RuntimeError("browser entry requires its Linux container")
    library = ctypes.CDLL(None, use_errno=True)
    library.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    library.prctl.restype = ctypes.c_int
    if library.prctl(4, 0, 0, 0, 0) != 0:  # Linux PR_SET_DUMPABLE=4, SUID_DUMP_DISABLE=0.
        raise RuntimeError("could not protect the trusted browser verifier")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
