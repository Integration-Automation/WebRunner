"""
跨 shard 事件總線：用檔案系統當 ndjson append-only log，避免引入 Redis。
File-based pub/sub event bus. Messages are JSON-encoded and appended to a
single file with ``O_APPEND``-style semantics (one ``open(mode="a")`` per
publish so concurrent writers don't tear). Subscribers tail the file from
a remembered offset; ``poll()`` returns every event newer than the last
seen position.

Designed for low-volume coordination signals (leader-elected setup
done / shard X started / N tests complete). For high-throughput logging
use a real broker.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class EventBusError(WebRunnerException):
    """Raised on invalid bus configuration or corrupted log lines."""


@dataclass
class EventEnvelope:
    event_id: str
    topic: str
    payload: Dict[str, Any]
    timestamp_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    sender: Optional[str] = None

    def to_json_line(self) -> str:
        return json.dumps({
            "event_id": self.event_id,
            "topic": self.topic,
            "payload": self.payload,
            "timestamp_ms": self.timestamp_ms,
            "sender": self.sender,
        }, ensure_ascii=False) + "\n"

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "EventEnvelope":
        try:
            return EventEnvelope(
                event_id=str(data["event_id"]),
                topic=str(data["topic"]),
                payload=data.get("payload") or {},
                timestamp_ms=int(data.get("timestamp_ms") or 0),
                sender=data.get("sender"),
            )
        except KeyError as error:
            raise EventBusError(f"event missing key {error.args[0]!r}") from error


@dataclass
class EventBus:
    """File-backed publish/subscribe primitive."""

    log_path: Union[str, Path]
    sender: Optional[str] = None
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _path(self) -> Path:
        return Path(self.log_path)

    def publish(self, topic: str, payload: Optional[Dict[str, Any]] = None) -> EventEnvelope:
        if not topic:
            raise EventBusError("topic must be non-empty")
        if payload is not None and not isinstance(payload, dict):
            raise EventBusError("payload must be dict or None")
        envelope = EventEnvelope(
            event_id=uuid.uuid4().hex,
            topic=topic,
            payload=payload or {},
            sender=self.sender,
        )
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = envelope.to_json_line().encode("utf-8")
        with self._lock:
            # ``O_APPEND`` keeps concurrent writers from clobbering each other
            # on POSIX; on Windows the std-lib file object handles append too.
            fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
        return envelope

    def poll(
        self,
        offset: int = 0,
        topics: Optional[Iterable[str]] = None,
    ) -> List[EventEnvelope]:
        path = self._path()
        if not path.is_file():
            return []
        topics_set = set(topics) if topics else None
        events: List[EventEnvelope] = []
        with open(path, "rb") as handle:
            handle.seek(offset)
            for raw_line in handle:
                if not raw_line.strip():
                    continue
                try:
                    data = json.loads(raw_line.decode("utf-8"))
                except ValueError as error:
                    raise EventBusError(f"corrupted log line: {error}") from error
                envelope = EventEnvelope.from_dict(data)
                if topics_set is None or envelope.topic in topics_set:
                    events.append(envelope)
        return events

    def current_offset(self) -> int:
        path = self._path()
        return path.stat().st_size if path.is_file() else 0

    def wait_for(
        self,
        topic: str,
        offset: int = 0,
        predicate: Optional[Callable[[EventEnvelope], bool]] = None,
        timeout: float = 30.0,
        poll_interval: float = 0.1,
        sleep: Callable[[float], None] = time.sleep,
    ) -> EventEnvelope:
        """Block until an event matching ``topic`` (and ``predicate``) appears."""
        deadline = time.monotonic() + timeout
        cursor = offset
        while time.monotonic() < deadline:
            events = self.poll(offset=cursor, topics=[topic])
            for envelope in events:
                if predicate is None or predicate(envelope):
                    return envelope
            cursor = self.current_offset()
            sleep(poll_interval)
        raise EventBusError(f"timed out waiting for topic {topic!r}")
