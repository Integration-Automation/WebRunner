"""
Per-test DB savepoint/rollback isolation, decoupled from the actual driver.
Tests that mutate shared state (orders, users, audit logs) used to leak
into each other; the usual workaround is to truncate everything between
tests, which is slow. This module takes a savepoint before the test runs
and rolls back to it after, regardless of pass/fail.

The driver isn't hard-coded: you implement :class:`SnapshotBackend` (two
methods, ``savepoint`` and ``rollback_to``) for psycopg / mysqlclient /
sqlite3 / SQLAlchemy / whatever you actually use. The included
:class:`InMemoryBackend` is for unit-testing the workflow itself.
"""
from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class DbSnapshotError(WebRunnerException):
    """Raised on backend failure, mis-ordered rollback, or invalid id."""


# ---------- backend protocol --------------------------------------------

class SnapshotBackend(Protocol):
    """Minimal DB interface: take a named savepoint, roll back to it."""

    def savepoint(self, name: str) -> None: ...
    def rollback_to(self, name: str) -> None: ...


# ---------- in-memory backend (for tests / dry runs) --------------------

@dataclass
class InMemoryBackend:
    """
    Simulates a DB with a single row dict per table. Used to exercise the
    snapshot workflow without a real database; also a useful fallback for
    `--dry-run` style unit tests.
    """

    tables: dict[str, dict[Any, Any]] = field(default_factory=dict)
    _snapshots: dict[str, dict[str, dict[Any, Any]]] = field(default_factory=dict)

    def insert(self, table: str, key: Any, value: Any) -> None:
        self.tables.setdefault(table, {})[key] = value

    def delete(self, table: str, key: Any) -> None:
        if table in self.tables:
            self.tables[table].pop(key, None)

    def savepoint(self, name: str) -> None:
        if name in self._snapshots:
            raise DbSnapshotError(f"savepoint {name!r} already exists")
        self._snapshots[name] = {t: dict(rows) for t, rows in self.tables.items()}
        web_runner_logger.info(f"db_snapshot in-memory savepoint {name!r}")

    def rollback_to(self, name: str) -> None:
        snap = self._snapshots.pop(name, None)
        if snap is None:
            raise DbSnapshotError(f"no savepoint named {name!r}")
        self.tables = {t: dict(rows) for t, rows in snap.items()}
        web_runner_logger.info(f"db_snapshot in-memory rollback to {name!r}")


# ---------- core scoping API --------------------------------------------

@dataclass
class SnapshotHandle:
    """Returned by :meth:`SnapshotScope.create`; pass back to :meth:`rollback`."""

    name: str


@dataclass
class SnapshotScope:
    """
    Stack of active snapshots, scoping cleanly via :func:`snapshot` ctx mgr.
    The stack lets nested test sections each take their own savepoint and
    unwind in the right order — rollback of a stale handle is rejected.
    """

    backend: SnapshotBackend
    prefix: str = "wr_snap"
    _stack: list[SnapshotHandle] = field(default_factory=list)

    def create(self) -> SnapshotHandle:
        name = f"{self.prefix}_{uuid.uuid4().hex[:12]}"
        try:
            self.backend.savepoint(name)
        except DbSnapshotError:
            raise
        except Exception as error:
            raise DbSnapshotError(f"backend.savepoint failed: {error!r}") from error
        handle = SnapshotHandle(name=name)
        self._stack.append(handle)
        return handle

    def rollback(self, handle: SnapshotHandle) -> None:
        if not self._stack:
            raise DbSnapshotError("no active snapshots to roll back")
        top = self._stack[-1]
        if top.name != handle.name:
            raise DbSnapshotError(
                f"snapshot stack mismatch: top is {top.name!r}, "
                f"got {handle.name!r} (rolled back out of order?)"
            )
        try:
            self.backend.rollback_to(handle.name)
        except DbSnapshotError:
            raise
        except Exception as error:
            raise DbSnapshotError(f"backend.rollback_to failed: {error!r}") from error
        self._stack.pop()

    def active(self) -> int:
        return len(self._stack)


@contextlib.contextmanager
def snapshot(scope: SnapshotScope):
    """Context manager: take a savepoint, roll back on exit (success or fail)."""
    handle = scope.create()
    try:
        yield handle
    finally:
        scope.rollback(handle)


# ---------- pytest helper (optional) ------------------------------------

def pytest_fixture_factory(backend: SnapshotBackend) -> Callable[..., Any]:
    """
    Build a pytest fixture that wraps each test in its own snapshot.
    Usage in ``conftest.py``::

        from je_web_runner.utils.db_snapshot.snapshot import (
            InMemoryBackend, pytest_fixture_factory,
        )
        backend = InMemoryBackend()
        db_snapshot = pytest_fixture_factory(backend)

    Then add ``db_snapshot`` as an argument on tests that need isolation.
    """
    scope = SnapshotScope(backend=backend)

    def _factory(*_args: Any, **_kwargs: Any):
        handle = scope.create()
        try:
            yield backend
        finally:
            scope.rollback(handle)

    return _factory


# ---------- convenience -------------------------------------------------

def assert_no_active_snapshots(scope: SnapshotScope) -> None:
    """Raise if any savepoint is still on the stack (use at suite teardown)."""
    if scope.active() > 0:
        raise DbSnapshotError(
            f"{scope.active()} snapshot(s) still active at teardown — "
            "test forgot to roll back"
        )
