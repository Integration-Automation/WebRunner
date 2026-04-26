"""
預先暖機的 browser instance pool；checkout / checkin 重複使用以省冷啟動。
Browser pool with warm sessions. Pre-launches up to ``size`` browser
instances (Selenium driver or Playwright page) and hands them out via
``checkout`` / context-manager. Checked-in sessions are health-checked
and recycled if the predicate fails or ``max_uses`` is exceeded.

The factory and health-check are caller-provided so the pool stays
backend-agnostic.
"""
from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any, Callable, Iterator, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class BrowserPoolError(WebRunnerException):
    """Raised when checkout times out or factory fails."""


@dataclass
class PooledSession:
    """Single browser session managed by the pool."""

    session_id: int
    instance: Any
    uses: int = 0
    created_at: float = field(default_factory=time.monotonic)


SessionFactory = Callable[[], Any]
SessionDestructor = Callable[[Any], None]
HealthCheck = Callable[[Any], bool]


class BrowserPool:
    """Thread-safe browser instance pool."""

    def __init__(
        self,
        factory: SessionFactory,
        destructor: Optional[SessionDestructor] = None,
        health_check: Optional[HealthCheck] = None,
        size: int = 2,
        max_uses: int = 50,
    ) -> None:
        if size <= 0:
            raise BrowserPoolError("size must be > 0")
        if max_uses <= 0:
            raise BrowserPoolError("max_uses must be > 0")
        self._factory = factory
        self._destructor = destructor or (lambda _instance: None)
        self._health_check = health_check or (lambda _instance: True)
        self._size = size
        self._max_uses = max_uses
        self._available: "Queue[PooledSession]" = Queue()
        self._lock = threading.Lock()
        self._next_id = 1
        self._closed = False
        self._tracked: List[PooledSession] = []

    def warm(self) -> None:
        """Pre-launch ``size`` instances eagerly."""
        for _ in range(self._size):
            session = self._spawn()
            self._available.put(session)

    def _spawn(self) -> PooledSession:
        try:
            instance = self._factory()
        except Exception as error:
            raise BrowserPoolError(f"factory failed: {error!r}") from error
        with self._lock:
            session_id = self._next_id
            self._next_id += 1
            session = PooledSession(session_id=session_id, instance=instance)
            self._tracked.append(session)
        web_runner_logger.info(f"browser_pool spawn id={session_id}")
        return session

    def checkout(self, timeout: float = 30.0) -> PooledSession:
        if self._closed:
            raise BrowserPoolError("pool is closed")
        deadline = time.monotonic() + timeout
        while True:
            session = self._acquire_session(timeout, deadline)
            if not self._is_healthy(session):
                self._destroy(session)
                continue
            return session

    def _acquire_session(self, timeout: float, deadline: float) -> PooledSession:
        try:
            return self._available.get_nowait()
        except Empty:
            pass
        if self._can_grow():
            return self._spawn()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BrowserPoolError(f"no session available within {timeout}s")
        try:
            return self._available.get(timeout=remaining)
        except Empty:
            raise BrowserPoolError(
                f"no session available within {timeout}s"
            ) from None

    def checkin(self, session: PooledSession) -> None:
        if self._closed:
            self._destroy(session)
            return
        session.uses += 1
        if session.uses >= self._max_uses or not self._is_healthy(session):
            self._destroy(session)
            return
        self._available.put(session)

    @contextlib.contextmanager
    def session(self, timeout: float = 30.0) -> Iterator[PooledSession]:
        ses = self.checkout(timeout=timeout)
        try:
            yield ses
        finally:
            self.checkin(ses)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            tracked = list(self._tracked)
            self._tracked.clear()
        while not self._available.empty():
            try:
                self._available.get_nowait()
            except Empty:
                break
        for session in tracked:
            self._destroy(session)

    def _is_healthy(self, session: PooledSession) -> bool:
        try:
            return bool(self._health_check(session.instance))
        except Exception as error:  # pylint: disable=broad-except
            web_runner_logger.debug(
                f"browser_pool health-check raised id={session.session_id}: {error!r}"
            )
            return False

    def _destroy(self, session: PooledSession) -> None:
        try:
            self._destructor(session.instance)
        except Exception as error:  # pylint: disable=broad-except
            web_runner_logger.warning(
                f"browser_pool destructor raised id={session.session_id}: {error!r}"
            )
        with self._lock:
            self._tracked = [s for s in self._tracked if s.session_id != session.session_id]

    def _can_grow(self) -> bool:
        with self._lock:
            return len(self._tracked) < self._size

    @property
    def tracked_count(self) -> int:
        with self._lock:
            return len(self._tracked)
