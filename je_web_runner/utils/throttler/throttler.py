"""
跨 shard 限制同時打同一個 service 的 client 數量。
Cross-process service throttling using filesystem-based slot files.

Each service has at most ``capacity`` slot files; ``acquire`` claims an
unused slot atomically by ``os.O_CREAT | os.O_EXCL``. ``release`` removes
the slot. Process death leaks slots; ``stale_after`` lets older slot files
be reclaimed after that many seconds.
"""
from __future__ import annotations

import contextlib
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ThrottlerError(WebRunnerException):
    """Raised when a slot cannot be acquired in time."""


@dataclass
class FileSemaphore:
    """File-based counting semaphore on a shared directory."""

    name: str
    capacity: int
    base_dir: str
    stale_after: float = 600.0

    def _service_dir(self) -> Path:
        directory = Path(self.base_dir) / self.name
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _reap_stale(self, directory: Path) -> None:
        if self.stale_after <= 0:
            return
        cutoff = time.time() - self.stale_after
        for entry in directory.iterdir():
            try:
                if entry.is_file() and entry.stat().st_mtime < cutoff:
                    entry.unlink(missing_ok=True)
            except OSError:
                continue

    def _try_acquire_one(self, directory: Path) -> Optional[Path]:
        for index in range(self.capacity):
            slot = directory / f"slot-{index}.lock"
            try:
                handle = os.open(str(slot), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                continue
            os.write(handle, f"{os.getpid()}|{uuid.uuid4().hex}\n".encode("utf-8"))
            os.close(handle)
            return slot
        return None

    def acquire(self, timeout: float = 30.0, poll: float = 0.1) -> Path:
        directory = self._service_dir()
        deadline = time.monotonic() + timeout
        while True:
            self._reap_stale(directory)
            claimed = self._try_acquire_one(directory)
            if claimed is not None:
                return claimed
            if time.monotonic() >= deadline:
                raise ThrottlerError(
                    f"unable to acquire slot for {self.name!r} within {timeout}s"
                )
            time.sleep(poll)

    def release(self, slot: Path) -> None:
        try:
            slot.unlink(missing_ok=True)
        except OSError as error:
            web_runner_logger.warning(f"throttler release {slot} failed: {error!r}")


class ServiceThrottler:
    """Manage multiple named semaphores under a single base directory."""

    def __init__(self, base_dir: str = ".webrunner/throttle") -> None:
        self.base_dir = base_dir
        self._semaphores: dict = {}

    def configure(self, name: str, capacity: int, stale_after: float = 600.0) -> None:
        if capacity <= 0:
            raise ThrottlerError(f"capacity for {name!r} must be > 0")
        self._semaphores[name] = FileSemaphore(
            name=name,
            capacity=capacity,
            base_dir=self.base_dir,
            stale_after=stale_after,
        )

    def get(self, name: str) -> FileSemaphore:
        if name not in self._semaphores:
            raise ThrottlerError(f"service {name!r} not configured")
        return self._semaphores[name]


_GLOBAL = ServiceThrottler()


def acquire(name: str, timeout: float = 30.0) -> Path:
    """Acquire a slot from the module-level throttler."""
    return _GLOBAL.get(name).acquire(timeout=timeout)


@contextlib.contextmanager
def throttle(name: str, timeout: float = 30.0) -> Iterator[Path]:
    """Context-manager wrapper around acquire/release."""
    sem = _GLOBAL.get(name)
    slot = sem.acquire(timeout=timeout)
    try:
        yield slot
    finally:
        sem.release(slot)


def configure_global(name: str, capacity: int,
                     base_dir: Optional[str] = None,
                     stale_after: float = 600.0) -> None:
    """Configure the module-level throttler."""
    if base_dir is not None:
        _GLOBAL.base_dir = base_dir
    _GLOBAL.configure(name=name, capacity=capacity, stale_after=stale_after)
