"""
Synthetic monitoring：固定 subset 對 prod 持續輪播，狀態變化時呼叫 alert sink。
Synthetic monitoring loop. Repeatedly executes the supplied check
callable; tracks per-check pass/fail state and only fires the alert sink
on edge transitions (``green→red`` and ``red→green``) so a continuously
red probe doesn't spam the channel.

The runner is dependency-light — pass any callable as the check and any
callable as the alert sink, so callers can wire to the existing
``webhook_notifier`` / Slack / PagerDuty without taking a new dep.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SyntheticMonitorError(WebRunnerException):
    """Raised on bad config or sink misuse."""


CheckCallable = Callable[[], Any]
AlertSink = Callable[[Dict[str, Any]], None]


@dataclass
class _CheckState:
    name: str
    last_status: Optional[str] = None  # "green" / "red"
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_error: Optional[str] = None
    last_run_at: Optional[float] = None


@dataclass
class SyntheticMonitorResult:
    """Per-iteration outcome for a single check."""

    name: str
    status: str  # "green" / "red"
    duration_seconds: float
    transitioned: bool
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "duration_seconds": round(self.duration_seconds, 4),
            "transitioned": self.transitioned,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class _ConfiguredCheck:
    name: str
    check: CheckCallable
    failure_threshold: int = 1   # consecutive fails before raising alert
    recovery_threshold: int = 1  # consecutive passes before clearing


class SyntheticMonitor:
    """Run a curated set of checks repeatedly, emitting alerts on transitions."""

    def __init__(
        self,
        alert_sink: AlertSink,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not callable(alert_sink):
            raise SyntheticMonitorError("alert_sink must be callable")
        self._alert_sink = alert_sink
        self._clock = clock
        self._checks: Dict[str, _ConfiguredCheck] = {}
        self._states: Dict[str, _CheckState] = {}

    def register(
        self,
        name: str,
        check: CheckCallable,
        failure_threshold: int = 1,
        recovery_threshold: int = 1,
    ) -> None:
        if not name:
            raise SyntheticMonitorError("check name must be non-empty")
        if not callable(check):
            raise SyntheticMonitorError("check must be callable")
        if failure_threshold < 1 or recovery_threshold < 1:
            raise SyntheticMonitorError("thresholds must be >= 1")
        self._checks[name] = _ConfiguredCheck(
            name=name,
            check=check,
            failure_threshold=failure_threshold,
            recovery_threshold=recovery_threshold,
        )
        self._states[name] = _CheckState(name=name)

    def tick_once(self) -> List[SyntheticMonitorResult]:
        """Run every registered check exactly once and return the outcomes."""
        results: List[SyntheticMonitorResult] = []
        for configured in self._checks.values():
            results.append(self._run_check(configured))
        return results

    def run_for(
        self,
        iterations: int,
        interval_seconds: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> List[SyntheticMonitorResult]:
        """Run ``iterations`` ticks separated by ``interval_seconds``."""
        if iterations <= 0:
            raise SyntheticMonitorError("iterations must be > 0")
        if interval_seconds < 0:
            raise SyntheticMonitorError("interval_seconds must be >= 0")
        all_results: List[SyntheticMonitorResult] = []
        for index in range(iterations):
            all_results.extend(self.tick_once())
            if index + 1 < iterations and interval_seconds > 0:
                sleep(interval_seconds)
        return all_results

    def _run_check(self, configured: _ConfiguredCheck) -> SyntheticMonitorResult:
        state = self._states[configured.name]
        start = self._clock()
        try:
            configured.check()
            error_text = None
        except Exception as error:  # pylint: disable=broad-except
            error_text = repr(error)
        duration = max(0.0, self._clock() - start)
        if error_text is None:
            state.consecutive_successes += 1
            state.consecutive_failures = 0
        else:
            state.consecutive_failures += 1
            state.consecutive_successes = 0
            state.last_error = error_text
        state.last_run_at = time.time()
        next_status, transitioned = self._next_status(state, configured)
        result = SyntheticMonitorResult(
            name=configured.name,
            status=next_status,
            duration_seconds=duration,
            transitioned=transitioned,
            error=error_text,
        )
        if transitioned:
            self._alert_sink({
                "event": "synthetic.transition",
                "check": configured.name,
                "previous": state.last_status,
                "current": next_status,
                "error": error_text,
                "duration_seconds": result.duration_seconds,
            })
        state.last_status = next_status
        return result

    def _next_status(
        self,
        state: _CheckState,
        configured: _ConfiguredCheck,
    ) -> tuple:
        previous = state.last_status
        if state.consecutive_failures >= configured.failure_threshold:
            current = "red"
        elif state.consecutive_successes >= configured.recovery_threshold:
            current = "green"
        else:
            # under threshold: keep prior status, default to green on cold start
            current = previous or "green"
        transitioned = previous is not None and previous != current
        return current, transitioned


def from_action_files(
    files: Iterable[Union[str]],
    runner: Callable[[str], None],
    *,
    failure_threshold: int = 2,
    recovery_threshold: int = 1,
    alert_sink: Optional[AlertSink] = None,
) -> SyntheticMonitor:
    """
    Build a monitor whose checks each run an action JSON file via ``runner``.
    """
    if alert_sink is None:
        def alert_sink(_payload):  # type: ignore[misc]
            return None
    monitor = SyntheticMonitor(alert_sink=alert_sink)
    for file_path in files:
        target = file_path

        def make_check(captured_path: str) -> CheckCallable:
            def check() -> None:
                runner(captured_path)
            return check

        monitor.register(
            name=str(target),
            check=make_check(str(target)),
            failure_threshold=failure_threshold,
            recovery_threshold=recovery_threshold,
        )
    return monitor
