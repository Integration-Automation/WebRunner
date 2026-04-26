"""
Playwright tracing 包裝：start / stop / 永遠輸出 .zip 給 ``playwright show-trace``。
Thin wrapper around Playwright's tracing API. Always emits a ``.zip`` so
the official ``playwright show-trace <file>`` viewer works without extra
glue.

Usage::

    recorder = TraceRecorder(output_dir="trace-out")
    recorder.start(context, name="login_flow")
    try:
        page.goto("https://example.com")
    finally:
        recorder.stop(context)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class TraceRecorderError(WebRunnerException):
    """Raised when tracing API isn't available or stop() runs without start()."""


@dataclass
class TraceRecorder:
    """Capture Playwright tracing into per-name zip files."""

    output_dir: str = "trace-out"
    screenshots: bool = True
    snapshots: bool = True
    sources: bool = True
    _active_name: Optional[str] = field(default=None, init=False)
    _written: List[str] = field(default_factory=list, init=False)

    def start(self, context: Any, name: str) -> None:
        if not name:
            raise TraceRecorderError("trace name required")
        if self._active_name is not None:
            raise TraceRecorderError(
                f"trace already active for {self._active_name!r}; call stop() first"
            )
        if not hasattr(context, "tracing"):
            raise TraceRecorderError("context.tracing missing — Playwright only")
        try:
            context.tracing.start(
                screenshots=self.screenshots,
                snapshots=self.snapshots,
                sources=self.sources,
                name=name,
            )
        except Exception as error:  # pylint: disable=broad-except
            raise TraceRecorderError(f"tracing.start failed: {error!r}") from error
        self._active_name = name
        web_runner_logger.info(f"trace started: {name!r}")

    def stop(self, context: Any) -> str:
        if self._active_name is None:
            raise TraceRecorderError("no trace is active")
        if not hasattr(context, "tracing"):
            raise TraceRecorderError("context.tracing missing — Playwright only")
        target = Path(self.output_dir) / f"{self._active_name}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            context.tracing.stop(path=str(target))
        except Exception as error:  # pylint: disable=broad-except
            raise TraceRecorderError(f"tracing.stop failed: {error!r}") from error
        web_runner_logger.info(f"trace stopped: {target}")
        self._written.append(str(target))
        self._active_name = None
        return str(target)

    def written(self) -> List[str]:
        return list(self._written)
