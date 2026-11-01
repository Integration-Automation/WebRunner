"""Fenced single-host watch ownership, health heartbeats and drain requests."""
from __future__ import annotations

import logging
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from typing import Any, Iterator

from je_web_runner.utils.issue_worker.store import IssueStore
from je_web_runner.utils.issue_worker.types import IssueWorkerError

HEARTBEAT_SECONDS = 10
STALE_SECONDS = 45


class WorkerRuntime:
    """Separate daemon ownership from per-job leases; preserve stopped health for inspection."""

    def __init__(self, store: IssueStore) -> None:
        self.store = store
        self.token: str | None = None
        self.lost = threading.Event()
        with store.connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS worker_runtime (
                id INTEGER PRIMARY KEY CHECK(id=1), token TEXT NOT NULL, pid INTEGER NOT NULL,
                started REAL NOT NULL, heartbeat REAL NOT NULL, active INTEGER NOT NULL,
                phase TEXT NOT NULL, current_issue TEXT, last_poll REAL, error TEXT,
                stop_requested INTEGER NOT NULL DEFAULT 0
            )""")

    def health(self) -> dict[str, Any]:
        """Read local state without contacting model or platform services."""
        with self.store.connection() as connection:
            row = connection.execute("SELECT * FROM worker_runtime WHERE id=1").fetchone()
        if row is None:
            return {"status": "stopped", "active": False, "stop_requested": False}
        result = dict(row)
        result["instance"] = result.pop("token")
        result["active"] = bool(result["active"])
        result["stop_requested"] = bool(result["stop_requested"])
        status = "healthy"
        if not result["active"]:
            status = "stopped"
        elif result["heartbeat"] < time.time() - STALE_SECONDS:
            status = "stale"
        elif result["error"]:
            status = "degraded"
        result["status"] = status
        return result

    def request_stop(self) -> bool:
        """Atomically target only the current live instance; leave no future stop flag."""
        with self.store.connection() as connection:
            cursor = connection.execute(
                "UPDATE worker_runtime SET stop_requested=1 WHERE id=1 AND active=1 AND heartbeat>=?",
                (time.time() - STALE_SECONDS,),
            )
            return cursor.rowcount == 1

    def assert_allowed(self) -> None:
        """Fence stale daemons and refuse manual run while another watch owns this directory."""
        if self.lost.is_set():
            raise IssueWorkerError("watch ownership was lost")
        health = self.health()
        if self.token:
            if health.get("instance") != self.token or health["status"] in {"stopped", "stale"}:
                raise IssueWorkerError("watch ownership was lost")
        elif health["active"] and health["status"] != "stale":
            raise IssueWorkerError("another watch owns this state directory")

    def stopping(self) -> bool:
        """Check the current instance's drain request without affecting a successor."""
        self.assert_allowed()
        return bool(self.health().get("stop_requested"))

    def update(self, phase: str, current_issue: str | None = None,
               error: str | None = None, polled: bool = False) -> None:
        """Checkpoint operational state; caller must sanitize errors first."""
        self.assert_allowed()
        with self.store.connection() as connection:
            cursor = connection.execute(
                "UPDATE worker_runtime SET phase=?,current_issue=?,error=?,last_poll=COALESCE(?,last_poll) "
                "WHERE id=1 AND token=? AND active=1 AND heartbeat>=?",
                (phase, current_issue, error, time.time() if polled else None, self.token,
                 time.time() - STALE_SECONDS),
            )
            if cursor.rowcount != 1:
                raise IssueWorkerError("watch ownership was lost")

    def begin_job(self, key: str) -> bool:
        """Atomically order drain requests against taking the next job."""
        self.assert_allowed()
        with self.store.connection() as connection:
            cursor = connection.execute(
                "UPDATE worker_runtime SET phase='processing',current_issue=? "
                "WHERE token=? AND active=1 AND stop_requested=0 AND heartbeat>=?",
                (key, self.token, time.time() - STALE_SECONDS),
            )
        if cursor.rowcount:
            return True
        self.assert_allowed()
        return False

    @contextmanager
    def own(self) -> Iterator[None]:
        """Claim daemon ownership, heartbeat independently of long checks, release only our row."""
        self._acquire()
        stopped = threading.Event()
        thread = threading.Thread(target=self._renew, args=(stopped, self.token, self.lost), daemon=True)
        thread.start()
        try:
            yield
            self.assert_allowed()
        finally:
            stopped.set()
            thread.join(timeout=12)
            try:
                with self.store.connection() as connection:
                    connection.execute("UPDATE worker_runtime SET active=0,phase='stopped' WHERE token=?",
                                       (self.token,))
            finally:
                self.token = None

    def _acquire(self) -> None:
        token = secrets.token_hex(16)
        now = time.time()
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT active,heartbeat FROM worker_runtime WHERE id=1").fetchone()
            job = connection.execute("SELECT expires FROM lease WHERE id=1").fetchone()
            if row and row["active"] and row["heartbeat"] >= now - STALE_SECONDS:
                raise IssueWorkerError("another watch owns this state directory")
            if job and job["expires"] > now:
                raise IssueWorkerError("another issue job is active")
            connection.execute(
                "INSERT OR REPLACE INTO worker_runtime "
                "(id,token,pid,started,heartbeat,active,phase,stop_requested) VALUES(1,?,?,?,?,1,'starting',0)",
                (token, os.getpid(), now, now),
            )
        self.token = token
        self.lost = threading.Event()

    def _renew(self, stopped: threading.Event, token: str | None, lost: threading.Event) -> None:
        while not stopped.wait(HEARTBEAT_SECONDS):
            try:
                with self.store.connection() as connection:
                    cursor = connection.execute(
                        "UPDATE worker_runtime SET heartbeat=? WHERE token=? AND active=1 AND heartbeat>=?",
                        (time.time(), token, time.time() - STALE_SECONDS),
                    )
                    if cursor.rowcount == 1:
                        continue
            except sqlite3.Error:
                lost.set()
                return
            lost.set()
            return


@contextmanager
def operational_log(store: IssueStore) -> Iterator[logging.Logger]:
    """One rotating log per watch owner; model context and issue text never enter this logger."""
    directory = store.root / "logs"
    directory.mkdir(exist_ok=True)
    handler = RotatingFileHandler(directory / "worker.log", maxBytes=5 * 1024 * 1024, backupCount=5,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.Logger("webrunner.issue.watch", level=logging.INFO)
    logger.addHandler(handler)
    try:
        yield logger
    finally:
        handler.close()
        logger.removeHandler(handler)
