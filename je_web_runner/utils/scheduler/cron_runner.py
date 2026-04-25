"""
排程執行：依固定間隔重跑 action JSON 檔。
Lightweight scheduled runner. Uses ``sched`` from the stdlib so no extra
dependency is required; for full cron syntax pair with APScheduler / cron
on the host instead.
"""
from __future__ import annotations

import sched
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class SchedulerError(WebRunnerException):
    """Raised when a job cannot be scheduled or executed."""


class ScheduledRunner:
    """Holds a list of (name, interval_seconds, callable) jobs and runs them on a sched."""

    def __init__(self) -> None:
        self._scheduler = sched.scheduler(time.monotonic, time.sleep)
        self._jobs: List[Dict[str, Any]] = []
        self._stop_event = threading.Event()
        self._counts: Dict[str, int] = {}

    def add(self, name: str, interval_seconds: float, callback: Callable[[], Any]) -> None:
        """Register a job; takes effect once ``run_for`` / ``run_forever`` is called."""
        if interval_seconds <= 0:
            raise SchedulerError(f"interval_seconds must be > 0 (got {interval_seconds})")
        self._jobs.append({
            "name": name,
            "interval": float(interval_seconds),
            "callback": callback,
        })
        self._counts[name] = 0

    def counts(self) -> Dict[str, int]:
        """Number of times each job has fired (since the last clear)."""
        return dict(self._counts)

    def stop(self) -> None:
        self._stop_event.set()

    def _enqueue(self, job: Dict[str, Any]) -> None:
        def _fire():
            if self._stop_event.is_set():
                return
            try:
                job["callback"]()
                self._counts[job["name"]] = self._counts.get(job["name"], 0) + 1
            except Exception as error:  # noqa: BLE001 — schedulers must keep running
                web_runner_logger.error(f"scheduled job {job['name']!r} raised: {error!r}")
            self._enqueue(job)
        self._scheduler.enter(job["interval"], 1, _fire)

    def run_for(self, seconds: float) -> None:
        """Run the scheduler for ``seconds`` then stop."""
        web_runner_logger.info(f"scheduler.run_for: {seconds}")
        self._stop_event.clear()
        for job in self._jobs:
            self._enqueue(job)
        deadline = time.monotonic() + max(float(seconds), 0.0)
        timer = threading.Timer(max(float(seconds), 0.0), self.stop)
        timer.daemon = True
        timer.start()
        try:
            while not self._stop_event.is_set() and time.monotonic() < deadline + 0.1:
                # ``sched.run(blocking=False)`` returns the delay until the
                # next event so we cooperate with ``stop()``.
                next_delay = self._scheduler.run(blocking=False)
                if next_delay is None:
                    break
                time.sleep(min(next_delay, 0.05))
        finally:
            timer.cancel()
            self._stop_event.set()

    def run_forever(self) -> None:
        """Block forever (until ``KeyboardInterrupt`` / ``stop()``)."""
        web_runner_logger.info("scheduler.run_forever")
        self._stop_event.clear()
        for job in self._jobs:
            self._enqueue(job)
        try:
            while not self._stop_event.is_set():
                next_delay = self._scheduler.run(blocking=False)
                if next_delay is None:
                    break
                time.sleep(min(next_delay, 0.5))
        except KeyboardInterrupt:
            self._stop_event.set()


_runner = ScheduledRunner()


def schedule(name: str, interval_seconds: float, callback: Callable[[], Any]) -> None:
    _runner.add(name, interval_seconds, callback)


def run_scheduler_for(seconds: float) -> None:
    _runner.run_for(seconds)


def run_scheduler_forever() -> None:
    _runner.run_forever()


def stop_scheduler() -> None:
    _runner.stop()


def scheduler_counts() -> Dict[str, int]:
    return _runner.counts()


def reset_scheduler() -> None:
    """Drop all registered jobs and counts (mainly for tests)."""
    global _runner
    _runner = ScheduledRunner()
