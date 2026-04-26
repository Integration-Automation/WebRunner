"""Workspace lock file: pin Python deps + driver versions + Playwright browsers."""
from je_web_runner.utils.workspace_lock.lock import (
    LockEntry,
    WorkspaceLock,
    WorkspaceLockError,
    load_lock,
    write_lock,
)

__all__ = [
    "LockEntry",
    "WorkspaceLock",
    "WorkspaceLockError",
    "load_lock",
    "write_lock",
]
