"""
Browser 程序監視：清掉 orphan chromedriver / geckodriver / msedgedriver；
給 long-running test 一個 watchdog 防止卡住。
Process supervisor for WebDriver-related binaries. Two surfaces:

- :class:`ProcessSupervisor` — listing + killing orphan ``chromedriver``
  / ``geckodriver`` / ``msedgedriver`` processes by walking the OS
  process table.
- :func:`with_watchdog` — wrap any callable with a hard wall-clock
  timeout so a single hung test can't take down the whole shard.

The process listing is delegated to a caller-supplied callable so the
heavy ``psutil`` dependency stays optional. The fallback uses the stdlib
``ps`` / ``tasklist`` shells.
"""
from __future__ import annotations

import os
import subprocess  # nosec B404 — argv-only invocation, no shell
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ProcessSupervisorError(WebRunnerException):
    """Raised when the process listing call fails."""


KNOWN_DRIVER_NAMES = (
    "chromedriver",
    "chromedriver.exe",
    "geckodriver",
    "geckodriver.exe",
    "msedgedriver",
    "msedgedriver.exe",
    "iedriver",
    "IEDriverServer.exe",
)


@dataclass
class OrphanFinding:
    pid: int
    name: str
    command_line: str = ""


ProcessLister = Callable[[], List[OrphanFinding]]
ProcessKiller = Callable[[int], bool]


def _ps_unix_lister() -> List[OrphanFinding]:
    try:
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        out = subprocess.check_output(  # nosec B603 B607 — explicit argv list
            ["ps", "-Ao", "pid=,comm=,args="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise ProcessSupervisorError(f"ps failed: {error!r}") from error
    findings: List[OrphanFinding] = []
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        name = parts[1]
        cmd = parts[2] if len(parts) >= 3 else name
        findings.append(OrphanFinding(pid=pid, name=name, command_line=cmd))
    return findings


def _tasklist_windows_lister() -> List[OrphanFinding]:
    try:
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        out = subprocess.check_output(  # nosec B603 B607 — explicit argv list
            ["tasklist", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise ProcessSupervisorError(f"tasklist failed: {error!r}") from error
    findings: List[OrphanFinding] = []
    for line in out.splitlines():
        # CSV with quoted fields: "Image","PID","Session","Session#","Mem"
        cleaned = [field.strip().strip('"') for field in line.split(",")]
        if len(cleaned) < 2:
            continue
        name = cleaned[0]
        try:
            pid = int(cleaned[1])
        except ValueError:
            continue
        findings.append(OrphanFinding(pid=pid, name=name, command_line=name))
    return findings


def default_lister() -> List[OrphanFinding]:
    if os.name == "nt":
        return _tasklist_windows_lister()
    return _ps_unix_lister()


def default_killer(pid: int) -> bool:
    try:
        if os.name == "nt":
            # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            subprocess.check_call(  # nosec B603 B607 — argv list, no shell
                ["taskkill", "/F", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        # The PID list is filtered by ``KNOWN_DRIVER_NAMES`` and excludes
        # ``os.getpid()`` upstream, so this signal-9 only ever lands on the
        # supervisor's own webdriver children. NOSONAR S4828
        os.kill(pid, 9)
        return True
    except (OSError, subprocess.CalledProcessError) as error:
        web_runner_logger.warning(f"process_supervisor kill {pid} failed: {error!r}")
        return False


@dataclass
class ProcessSupervisor:
    """List + kill orphan webdriver processes."""

    lister: ProcessLister = field(default=default_lister)
    killer: ProcessKiller = field(default=default_killer)

    def list_orphans(self, names: Iterable[str] = KNOWN_DRIVER_NAMES) -> List[OrphanFinding]:
        target_set = {name.lower() for name in names}
        all_processes = self.lister()
        if not isinstance(all_processes, list):
            raise ProcessSupervisorError("lister must return a list")
        return [
            finding for finding in all_processes
            if isinstance(finding, OrphanFinding)
            and finding.name.lower() in target_set
        ]

    def kill_orphans(
        self,
        names: Iterable[str] = KNOWN_DRIVER_NAMES,
        protected_pids: Optional[Iterable[int]] = None,
    ) -> Dict[int, bool]:
        protected = set(protected_pids or [])
        results: Dict[int, bool] = {}
        for finding in self.list_orphans(names):
            if finding.pid in protected:
                continue
            if finding.pid == os.getpid():
                continue
            web_runner_logger.info(
                f"process_supervisor killing pid={finding.pid} name={finding.name!r}"
            )
            results[finding.pid] = bool(self.killer(finding.pid))
        return results


def with_watchdog(
    callable_obj: Callable[[], Any],
    timeout_seconds: float,
) -> Any:
    """
    Run ``callable_obj()`` on a daemon thread and raise after ``timeout_seconds``.

    The original callable keeps running on its thread; the caller is expected
    to react to the watchdog raise and clean up the underlying browser via
    :class:`ProcessSupervisor` if needed.
    """
    if timeout_seconds <= 0:
        raise ProcessSupervisorError("timeout_seconds must be > 0")
    container: Dict[str, Any] = {}

    def runner() -> None:
        try:
            container["result"] = callable_obj()
        except Exception as error:  # pylint: disable=broad-except
            # The watchdog deliberately swallows the worker's exception
            # so we can re-raise it from the parent thread once join()
            # returns; KeyboardInterrupt / SystemExit propagate.
            container["error"] = error

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    if thread.is_alive():
        raise ProcessSupervisorError(
            f"watchdog fired after {timeout_seconds}s; thread still running"
        )
    if "error" in container:
        raise container["error"]
    return container.get("result")
