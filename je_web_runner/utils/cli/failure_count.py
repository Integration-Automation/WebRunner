"""
計算一次 CLI 執行中失敗了多少
Count what fails during one CLI run, for the exit status.

The executor records a failed action and runs the next one, so ``execute_action`` returns the
same way whether the run passed or not. :class:`FailureCount` wraps the executor's reporter for
the length of a ``with`` block and counts the actions that raised. Files run in another process
or on the asyncio executor never reach this process's reporter; their runner reports them with
:func:`note_failed_file`.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from threading import Lock
from types import TracebackType
from typing import Any

from je_action_core import ExecutionReporter

from je_web_runner.utils.executor.action_executor import executor


class _CountingReporter(ExecutionReporter):
    """Passes every event on to the executor's own reporter and counts the actions that raised."""

    def __init__(self, delegate: ExecutionReporter) -> None:
        self._delegate = delegate
        self._lock = Lock()
        self.raised = 0

    def add(self, count: int = 1) -> None:
        """Count ``count`` more failures (thread-safe: ``--parallel-mode=thread`` runs files on threads)."""
        with self._lock:
            self.raised += count

    def on_start(self, action_list: Any) -> None:
        self._delegate.on_start(action_list)

    def on_event(self, action: Any) -> None:
        self._delegate.on_event(action)

    def on_success(self, action: Any) -> None:
        self._delegate.on_success(action)

    def on_failure(self, action: Any, error: Exception) -> None:
        self.add()
        self._delegate.on_failure(action, error)

    def on_empty(self, action_list: Any) -> None:
        self._delegate.on_empty(action_list)

    def on_records(self, records: Mapping[str, Any]) -> None:
        self._delegate.on_records(records)


class FailureCount:
    """Counts what fails while its ``with`` block runs; ``failed`` is the total."""

    _active: FailureCount | None = None

    def __init__(self) -> None:
        self._settings = executor.settings
        self._reporter = _CountingReporter(self._settings.reporter)
        self._outer: FailureCount | None = None

    def __enter__(self) -> FailureCount:
        self._settings = executor.settings
        self._reporter = _CountingReporter(self._settings.reporter)
        executor.settings = replace(self._settings, reporter=self._reporter)
        self._outer = FailureCount._active
        FailureCount._active = self
        return self

    def __exit__(self, kind: type[BaseException] | None, error: BaseException | None,
                 trace: TracebackType | None) -> None:
        executor.settings = self._settings
        FailureCount._active = self._outer

    @property
    def failed(self) -> int:
        """How many actions raised, and files were reported as failed, since the block was entered."""
        return self._reporter.raised

    def _note(self) -> None:
        self._reporter.add()


def note_failed_file() -> None:
    """Count a file that failed where this process's executor could not see it; a no-op outside a count."""
    active = FailureCount._active  # pylint: disable=protected-access
    if active is not None:
        active._note()  # pylint: disable=protected-access
