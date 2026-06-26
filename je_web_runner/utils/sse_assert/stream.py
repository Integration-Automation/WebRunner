"""
Server-Sent Events stream assertions, 對稱 ``websocket_assert`` 的姊妹模組。
Parses the SSE wire format (``event: foo\\ndata: bar\\n\\n``) into
:class:`SseEvent`, lets the test record N of them, and exposes a fluent
set of count / event-type / data assertions.

Typical usage:

* Hook into CDP ``Network.eventSourceMessageReceived`` (or
  Playwright's ``page.on('response')`` + ``response.body()``).
* Push the raw chunk into :meth:`SseRecorder.feed`.
* Call ``assert_event_count`` / ``assert_received_event`` / ...
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SseAssertError(WebRunnerException):
    """Raised on malformed SSE input or failed assertions."""


# ---------- model -------------------------------------------------------

@dataclass
class SseEvent:
    """One parsed SSE event."""

    event: str = "message"  # default per SSE spec
    data: str = ""
    id: str | None = None
    retry: int | None = None
    timestamp: float = field(default_factory=time.time)

    def as_json(self) -> Any:
        """Decode the data payload as JSON; raise if undecodable."""
        try:
            return json.loads(self.data)
        except ValueError as error:
            raise SseAssertError(
                f"event data is not JSON ({error}): {self.data[:80]!r}"
            ) from error

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------- parser ------------------------------------------------------

_FIELD_RE = re.compile(r"^([A-Za-z]+)(?::\s?(.*))?$")


def parse_sse_stream(text: str) -> list[SseEvent]:
    """
    Parse an SSE bytestream chunk into a list of :class:`SseEvent`.
    Robust to ``\\r\\n`` / ``\\n`` line endings and trailing partial events
    (returned only when terminated by a blank line).
    """
    if not isinstance(text, str):
        raise SseAssertError(f"parse_sse_stream expects str, got {type(text).__name__}")
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_events = normalised.split("\n\n")
    events: list[SseEvent] = []
    for raw in raw_events:
        if not raw.strip():
            continue
        event = _parse_event_block(raw)
        if event is not None:
            events.append(event)
    return events


def _parse_event_block(raw: str) -> SseEvent | None:  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    event_type = "message"
    data_lines: list[str] = []
    event_id: str | None = None
    retry: int | None = None
    for line in raw.split("\n"):
        if not line or line.startswith(":"):  # comment line
            continue
        match = _FIELD_RE.match(line)
        if not match:
            continue
        field_name = match.group(1).lower()
        value = match.group(2) or ""
        if field_name == "event":
            event_type = value
        elif field_name == "data":
            data_lines.append(value)
        elif field_name == "id":
            event_id = value
        elif field_name == "retry":
            try:
                retry = int(value)
            except ValueError:
                retry = None
    if not data_lines and event_type == "message" and event_id is None and retry is None:
        return None
    return SseEvent(
        event=event_type,
        data="\n".join(data_lines),
        id=event_id,
        retry=retry,
    )


# ---------- recorder ----------------------------------------------------

class SseRecorder:
    """Stateful chunk-feeder. Holds parsed events for assertion."""

    def __init__(self) -> None:
        self._events: list[SseEvent] = []
        self._buffer = ""

    def __len__(self) -> int:
        return len(self._events)

    def feed(self, chunk: str) -> int:
        """
        Append a chunk; parse any newly-terminated events from the buffer.
        Returns the number of events parsed from this call.
        """
        if not isinstance(chunk, str):
            raise SseAssertError(f"feed expects str, got {type(chunk).__name__}")
        self._buffer += chunk
        normalised = self._buffer.replace("\r\n", "\n").replace("\r", "\n")
        if "\n\n" not in normalised:
            self._buffer = normalised
            return 0
        complete, _, leftover = normalised.rpartition("\n\n")
        self._buffer = leftover
        new_events = parse_sse_stream(complete + "\n\n")
        self._events.extend(new_events)
        return len(new_events)

    def feed_event(self, event: SseEvent) -> None:
        if not isinstance(event, SseEvent):
            raise SseAssertError("feed_event expects SseEvent")
        self._events.append(event)

    def clear(self) -> None:
        self._events.clear()
        self._buffer = ""

    def events(self, *, event_type: str | None = None) -> list[SseEvent]:
        if event_type is None:
            return list(self._events)
        return [e for e in self._events if e.event == event_type]


# ---------- assertions --------------------------------------------------

def assert_event_count(
    recorder: SseRecorder,
    *,
    event_type: str | None = None,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    """Assert ``minimum <= count <= maximum`` for the filtered events."""
    if minimum < 0:
        raise SseAssertError("minimum must be >= 0")
    if maximum is not None and maximum < minimum:
        raise SseAssertError("maximum must be >= minimum")
    count = len(recorder.events(event_type=event_type))
    if count < minimum or (maximum is not None and count > maximum):
        raise SseAssertError(
            f"SSE event count out of range: got {count}, want "
            f"[{minimum}, {maximum if maximum is not None else 'inf'}] "
            f"(event_type={event_type!r})"
        )
    return count


def assert_received_event(
    recorder: SseRecorder,
    predicate: Callable[[SseEvent], bool],
    *,
    description: str = "event predicate",
) -> SseEvent:
    """Assert at least one event matches ``predicate``."""
    for event in recorder.events():
        try:
            if predicate(event):
                return event
        except Exception:  # nosec B112 — user predicate may legitimately raise; skip + continue
            continue
    raise SseAssertError(f"no SSE event matched: {description}")


def assert_data_contains(
    recorder: SseRecorder,
    needle: str,
    *,
    event_type: str | None = None,
) -> SseEvent:
    """Assert an event whose ``data`` contains ``needle``."""
    if not isinstance(needle, str) or not needle:
        raise SseAssertError("needle must be a non-empty string")
    for event in recorder.events(event_type=event_type):
        if needle in event.data:
            return event
    raise SseAssertError(
        f"no event with data containing {needle!r} (event_type={event_type})"
    )


def assert_json_shape(
    recorder: SseRecorder,
    required_keys: Sequence[str],
    *,
    event_type: str | None = None,
) -> SseEvent:
    """Assert a JSON-data event whose top-level dict has every ``required_keys``."""
    if not required_keys:
        raise SseAssertError("required_keys must be non-empty")
    wanted = set(required_keys)
    for event in recorder.events(event_type=event_type):
        try:
            obj = event.as_json()
        except SseAssertError:
            continue
        if isinstance(obj, dict) and wanted.issubset(obj.keys()):
            return event
    raise SseAssertError(
        f"no SSE event had keys {sorted(wanted)} (event_type={event_type})"
    )


def assert_strictly_increasing_ids(recorder: SseRecorder) -> None:
    """Assert ``id`` values, when present, are strictly increasing."""
    last: str | None = None
    for event in recorder.events():
        if event.id is None:
            continue
        if last is not None and event.id <= last:
            raise SseAssertError(
                f"SSE id not strictly increasing: {last!r} -> {event.id!r}"
            )
        last = event.id


def to_json(events: Iterable[SseEvent]) -> str:
    """Serialise events as a JSON array for failure-bundle attachment."""
    return json.dumps([e.to_dict() for e in events], ensure_ascii=False, indent=2)
