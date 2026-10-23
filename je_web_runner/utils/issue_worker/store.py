"""SQLite queue, checkpoints and a renewable single-worker lease."""
from __future__ import annotations

import json
import math
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from je_web_runner.utils.issue_worker.types import ACTIVE, FINAL, IssueSnapshot, IssueWorkerError


class IssueStore:
    """A local WAL database; no network filesystem or multi-host coordination is assumed."""

    def __init__(self, state_dir: str | Path, aging_per_hour: float = 5) -> None:
        if isinstance(aging_per_hour, bool) or not isinstance(aging_per_hour, (int, float)) or \
                not math.isfinite(aging_per_hour) or not 0 <= aging_per_hour <= 100:
            raise IssueWorkerError("invalid queue aging rate")
        self.root = Path(state_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "issues.sqlite3"
        self._local = threading.local()
        self.aging_per_hour = aging_per_hour
        with self.connection() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    key TEXT PRIMARY KEY, snapshot TEXT NOT NULL, status TEXT NOT NULL,
                    data TEXT NOT NULL DEFAULT '{}', run INTEGER NOT NULL DEFAULT 1,
                    created REAL NOT NULL, updated REAL NOT NULL, next_attempt REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS lease (id INTEGER PRIMARY KEY CHECK(id=1), token TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS review_events (
                    job_key TEXT NOT NULL, run INTEGER NOT NULL, event_key TEXT NOT NULL,
                    state TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(job_key,run,event_key)
                );
                CREATE TABLE IF NOT EXISTS outcomes (
                    job_key TEXT NOT NULL, run INTEGER NOT NULL, revision INTEGER NOT NULL,
                    payload TEXT NOT NULL, recorded REAL NOT NULL,
                    PRIMARY KEY(job_key,run,revision)
                );
            """)
            connection.execute("BEGIN IMMEDIATE")
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(jobs)")}
            for name, declaration in (("priority", "INTEGER NOT NULL DEFAULT 50"),
                                      ("suitable", "INTEGER NOT NULL DEFAULT 1")):
                if name not in columns:
                    connection.execute(f"ALTER TABLE jobs ADD COLUMN {name} {declaration}")
            connection.execute("INSERT OR IGNORE INTO settings VALUES('metrics_since',?)", (str(time.time()),))
            connection.execute("CREATE INDEX IF NOT EXISTS jobs_dispatch ON jobs(status,suitable,next_attempt)")
            connection.execute("""CREATE INDEX IF NOT EXISTS jobs_outbox ON jobs(created,key)
                WHERE instr(data,'"report_pending": true') > 0""")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Commit on success, rollback on failure, always close the connection."""
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def enqueue(self, snapshot: IssueSnapshot, triage: dict[str, Any] | None = None) -> bool:
        """Insert a source/id once; polling never overwrites an in-flight requirement snapshot."""
        now = time.time()
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO jobs(key,snapshot,status,created,updated,data,priority,suitable) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (snapshot.key, json.dumps(snapshot.to_dict()), "queued", now, now,
                 json.dumps({"triage": triage} if triage else {}), (triage or {}).get("priority", 50),
                 int((triage or {}).get("suitable", True))),
            )
            if not cursor.rowcount and triage is not None:
                self._refresh_queued(connection, snapshot, triage)
            return cursor.rowcount == 1

    @staticmethod
    def _refresh_queued(connection: sqlite3.Connection, snapshot: IssueSnapshot, triage: dict[str, Any]) -> None:
        row = connection.execute("SELECT snapshot,data,suitable FROM jobs WHERE key=? AND status='queued'",
                                 (snapshot.key,)).fetchone()
        if row is None:
            return
        data = json.loads(row["data"])
        if data.get("claim_started"):
            return
        data["triage"] = triage
        payload = json.dumps(snapshot.to_dict()) if not row["suitable"] or not triage["suitable"] else row["snapshot"]
        connection.execute("UPDATE jobs SET snapshot=?,data=?,priority=?,suitable=?,updated=? "
                           "WHERE key=? AND status='queued'", (payload, json.dumps(data), triage["priority"],
                                                               int(triage["suitable"]), time.time(), snapshot.key))

    def bind(self, scope: dict[str, str]) -> None:
        """A state directory cannot silently switch API origins or repository identity."""
        encoded = json.dumps(scope, sort_keys=True)
        with self.connection() as connection:
            connection.execute("INSERT OR IGNORE INTO settings VALUES('scope',?)", (encoded,))
            row = connection.execute("SELECT value FROM settings WHERE name='scope'").fetchone()
            if row["value"] != encoded:
                raise IssueWorkerError("state directory belongs to a different platform scope; use another directory")

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["snapshot"] = json.loads(result["snapshot"])
        result["data"] = json.loads(result["data"])
        return result

    def status(self, key: str | None = None) -> list[dict[str, Any]]:
        """Read persisted jobs in FIFO order."""
        with self.connection() as connection:
            rows = (connection.execute("SELECT * FROM jobs WHERE key=?", (key,)) if key else
                    connection.execute("SELECT * FROM jobs ORDER BY created,key"))
            return [self._decode(row) for row in rows]

    def next_job(self) -> dict[str, Any] | None:
        """Resume active work before taking the next queued item."""
        now = time.time()
        with self.connection() as connection:
            active = connection.execute(
                "SELECT * FROM jobs WHERE status IN (?,?,?,?,?) AND suitable=1 AND next_attempt<=? "
                "ORDER BY created,key LIMIT 1", (*sorted(ACTIVE), now),
            ).fetchone()
            if active:
                return self._decode(active)
            pending = connection.execute(
                "SELECT * FROM jobs WHERE instr(data,'\"report_pending\": true') > 0 AND next_attempt<=? "
                "ORDER BY created,key", (now,),
            )
            for row in pending:
                job = self._decode(row)
                if job["data"].get("report_pending"):
                    return job
            queued = connection.execute(
                "SELECT * FROM jobs WHERE status='queued' AND suitable=1 AND next_attempt<=? "
                "ORDER BY priority+MAX(0,?-created)/3600.0*? DESC,created,key LIMIT 1",
                (now, now, self.aging_per_hour),
            ).fetchone()
            return self._decode(queued) if queued else None

    def save(self, key: str, status: str, data: dict[str, Any], next_attempt: float = 0) -> None:
        """Persist a checkpoint before publishing any external side effect."""
        if status not in ACTIVE | FINAL | {"queued"}:
            raise IssueWorkerError("invalid worker status")
        with self.connection() as connection:
            connection.execute("UPDATE jobs SET status=?,data=?,updated=?,next_attempt=? WHERE key=?",
                               (status, json.dumps(data), time.time(), next_attempt, key))

    def retry(self, snapshot: IssueSnapshot, triage: dict[str, Any] | None = None) -> None:
        """Explicitly requeue a terminal job with fresh requirements and a new run identity."""
        with self.connection() as connection:
            cursor = connection.execute(
                "UPDATE jobs SET snapshot=?,status='queued',data=?,run=run+1,updated=?,next_attempt=0,"
                "priority=?,suitable=? "
                "WHERE key=? AND status IN ('needs_info','failed','cancelled')",
                (json.dumps(snapshot.to_dict()), json.dumps({"triage": triage} if triage else {}), time.time(),
                 (triage or {}).get("priority", 50), int((triage or {}).get("suitable", True)), snapshot.key),
            )
            if cursor.rowcount != 1:
                raise IssueWorkerError("only failed, cancelled or needs_info jobs may be retried")

    def review_seen(self, key: str, run: int) -> set[str]:
        """Return events already claimed/handled for a particular PR run."""
        with self.connection() as connection:
            rows = connection.execute("SELECT event_key FROM review_events WHERE job_key=? AND run=?",
                                      (key, run))
            return {row["event_key"] for row in rows}

    def start_review(self, job: dict[str, Any], events: list[dict[str, Any]]) -> None:
        """Atomically checkpoint a revision and claim its immutable feedback batch."""
        self.assert_lease()
        with self.connection() as connection:
            for event in events:
                connection.execute("INSERT INTO review_events VALUES(?,?,?,'processing',?)",
                                   (job["key"], job["run"], event["key"], json.dumps(event)))
            connection.execute("UPDATE jobs SET status='claimed',data=?,updated=?,next_attempt=0 WHERE key=?",
                               (json.dumps(job["data"]), time.time(), job["key"]))
        job["status"] = "claimed"

    def finish_review(self, job: dict[str, Any]) -> None:
        """Acknowledge feedback only after revision publication and progress delivery checkpoint."""
        self.assert_lease()
        with self.connection() as connection:
            connection.execute("UPDATE review_events SET state='handled' WHERE job_key=? AND run=?",
                               (job["key"], job["run"]))

    def resume_review(self, job: dict[str, Any], snapshot: IssueSnapshot) -> None:
        """Explicitly accept refreshed requirements without changing the PR/run identity."""
        self.assert_lease()
        data = job["data"]
        data.pop("review_blocked", None)
        data.pop("review_closed", None)
        data["review_polled"] = 0
        data["report_pending"] = False
        with self.connection() as connection:
            connection.execute("DELETE FROM review_events WHERE job_key=? AND run=? AND state='processing'",
                               (job["key"], job["run"]))
            connection.execute("UPDATE jobs SET snapshot=?,status='awaiting_review',data=?,updated=?,next_attempt=0 "
                               "WHERE key=?", (json.dumps(snapshot.to_dict()), json.dumps(data), time.time(),
                                               job["key"]))

    def record_outcome(self, job: dict[str, Any]) -> None:
        """Record each run/revision once; delivery metrics are not claims of business acceptance."""
        self.assert_lease()
        data = job["data"]
        if "finished_at" not in data:
            return  # Older pending reports are legacy observations, not newly measured completions.
        started = data.get("started_at")
        finished = data.get("finished_at", time.time())
        duration = max(0, finished - started) if isinstance(started, (int, float)) else None
        payload = {"key": job["key"], "run": job["run"], "revision": data.get("review_rounds", 0),
                   "source": job["snapshot"]["source"], "kind": data.get("analysis", {}).get("kind") or
                   data.get("triage", {}).get("kind", "unknown"), "status": job["status"],
                   "reason_code": data.get("reason_code", job["status"]), "reason": data.get("reason", "")[:1000],
                   "duration_seconds": duration, "tool_count": data.get("tool_count", 0),
                   "validation_rounds": data.get("validation_rounds", 0), "tree": data.get("validated_tree"),
                   "changes": data.get("change_summary", {}), "business_verified": False}
        with self.connection() as connection:
            connection.execute("INSERT OR IGNORE INTO outcomes VALUES(?,?,?,?,?)",
                               (job["key"], job["run"], payload["revision"], json.dumps(payload), finished))

    @contextmanager
    def lease(self) -> Iterator[None]:
        """One worker per database, with ten-second renewal and crash recovery after 30 seconds."""
        token = secrets.token_hex(16)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT expires FROM lease WHERE id=1").fetchone()
            if row and row["expires"] > time.time():
                raise IssueWorkerError("another issue worker is active")
            connection.execute("INSERT OR REPLACE INTO lease VALUES(1,?,?)", (token, time.time() + 30))
        stopped = threading.Event()
        self._local.token = token
        lost = threading.Event()
        thread = threading.Thread(target=self._renew, args=(token, stopped, lost), daemon=True)
        thread.start()
        try:
            yield
            if lost.is_set():
                raise IssueWorkerError("worker lease was lost")
        finally:
            stopped.set()
            thread.join(timeout=12)
            with self.connection() as connection:
                connection.execute("DELETE FROM lease WHERE token=?", (token,))
            self._local.token = None

    def _renew(self, token: str, stopped: threading.Event, lost: threading.Event) -> None:
        while not stopped.wait(10):
            try:
                with self.connection() as connection:
                    cursor = connection.execute("UPDATE lease SET expires=? WHERE token=?", (time.time() + 30, token))
                    if cursor.rowcount != 1:
                        lost.set()
                        return
            except sqlite3.Error:
                lost.set()
                return

    def assert_lease(self) -> None:
        """Require a live worker lease immediately before external publication."""
        with self.connection() as connection:
            row = connection.execute("SELECT token,expires FROM lease WHERE id=1").fetchone()
            if not row or row["expires"] <= time.time() or row["token"] != getattr(self._local, "token", None):
                raise IssueWorkerError("worker lease expired")
