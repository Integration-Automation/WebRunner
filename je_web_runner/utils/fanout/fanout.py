"""
Fan-out 同 test 內平行執行多個 callable：API 預檢、多 tab 並發。
Run multiple callables concurrently inside the same test, returning a
``FanOutResult`` with the per-task duration / outcome / exception so the
caller can decide whether to fail.

Designed for read-only / side-effect-free operations such as API
preflights, screenshot captures across viewports, or multiple HAR diffs;
do not use it to drive the same browser instance from two threads.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class FanOutError(WebRunnerException):
    """Raised when arguments are invalid or all tasks fail under fail_fast=True."""


@dataclass
class _TaskOutcome:
    name: str
    duration_seconds: float
    result: Any = None
    error: Optional[BaseException] = None

    @property
    def succeeded(self) -> bool:
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "duration_seconds": round(self.duration_seconds, 4),
            "succeeded": self.succeeded,
            "result": _safe_repr(self.result) if self.succeeded else None,
            "error": repr(self.error) if self.error else None,
        }


def _safe_repr(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, dict)):
        return value
    return repr(value)[:200]


@dataclass
class FanOutResult:
    outcomes: List[_TaskOutcome] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return all(o.succeeded for o in self.outcomes)

    @property
    def failures(self) -> List[_TaskOutcome]:
        return [o for o in self.outcomes if not o.succeeded]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "succeeded": self.succeeded,
            "outcomes": [o.to_dict() for o in self.outcomes],
        }

    def raise_for_failures(self) -> None:
        if self.succeeded:
            return
        sample = [
            {"name": o.name, "error": repr(o.error)} for o in self.failures[:5]
        ]
        raise FanOutError(f"{len(self.failures)} fan-out task(s) failed: {sample}")


_Task = Callable[[], Any]


def run_fan_out(
    tasks: Sequence[Any],
    max_workers: Optional[int] = None,
    timeout: Optional[float] = None,
    fail_fast: bool = False,
) -> FanOutResult:
    """
    平行跑多個 callable；每個 task 可以是 ``callable`` 或 ``(name, callable)`` tuple。
    Run every entry in ``tasks`` concurrently. Each entry must be either a
    zero-arg callable or a ``(name, callable)`` tuple. Returns a
    :class:`FanOutResult` with per-task timing and outcomes.
    """
    if not tasks:
        raise FanOutError("tasks must be non-empty")
    parsed = _parse_tasks(tasks)
    workers = max_workers or min(len(parsed), 8)
    result = FanOutResult()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_name = {
            pool.submit(_timed_run, name, fn): name
            for name, fn in parsed
        }
        _collect_results(future_to_name, result, timeout, fail_fast)
    web_runner_logger.info(
        f"fanout completed n={len(result.outcomes)} ok={result.succeeded}"
    )
    return result


def _parse_tasks(tasks: Sequence[Any]) -> List[tuple]:
    parsed: List[tuple] = []
    for index, entry in enumerate(tasks):
        if callable(entry):
            parsed.append((f"task-{index}", entry))
        elif isinstance(entry, tuple) and len(entry) == 2 and callable(entry[1]):
            parsed.append((str(entry[0]), entry[1]))
        else:
            raise FanOutError(f"tasks[{index}] must be callable or (name, callable)")
    return parsed


def _collect_results(future_to_name: Dict[Any, str], result: FanOutResult,
                     timeout: Optional[float], fail_fast: bool) -> None:
    try:
        for future in as_completed(future_to_name, timeout=timeout):
            outcome = future.result()
            result.outcomes.append(outcome)
            if fail_fast and not outcome.succeeded:
                for pending in future_to_name:
                    pending.cancel()
                break
    except TimeoutError as error:
        raise FanOutError(f"fan-out timed out after {timeout}s") from error


def _timed_run(name: str, fn: _Task) -> _TaskOutcome:
    start = time.monotonic()
    try:
        value = fn()
        return _TaskOutcome(name=name, duration_seconds=time.monotonic() - start,
                            result=value)
    except Exception as error:  # pylint: disable=broad-except
        return _TaskOutcome(name=name, duration_seconds=time.monotonic() - start,
                            error=error)
