"""
把 OTel span / console message / HTTP response 對齊到單一時間軸。
Merge OpenTelemetry spans, captured console messages, and network responses
into a single chronological event stream so debugging UIs can render them
on one row.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class TimelineError(WebRunnerException):
    """Raised when an event lacks a usable timestamp."""


@dataclass
class TimelineEvent:
    """A single point on the merged timeline."""

    timestamp_ms: float
    kind: str
    label: str
    payload: Dict[str, Any]


def _coerce_timestamp(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _first_present(source: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in source:
            return source[key]
    return None


def from_spans(spans: Iterable[Dict[str, Any]]) -> List[TimelineEvent]:
    """Convert OTel-shaped spans (``{name, start_ms, end_ms, attrs}``)."""
    events: List[TimelineEvent] = []
    for span in spans:
        start = _coerce_timestamp(_first_present(span, "start_ms", "start"))
        end = _coerce_timestamp(_first_present(span, "end_ms", "end"))
        name = str(span.get("name") or "span")
        if start is None:
            continue
        attrs = span.get("attrs") or {}
        events.append(TimelineEvent(
            timestamp_ms=start,
            kind="span.start",
            label=name,
            payload={"end_ms": end, "attrs": attrs},
        ))
        if end is not None:
            events.append(TimelineEvent(
                timestamp_ms=end,
                kind="span.end",
                label=name,
                payload={"duration_ms": end - start},
            ))
    return events


def from_console(messages: Iterable[Dict[str, Any]]) -> List[TimelineEvent]:
    events: List[TimelineEvent] = []
    for index, message in enumerate(messages):
        ts = _coerce_timestamp(_first_present(message, "timestamp_ms", "ts"))
        if ts is None:
            ts = float(index)  # preserve order even when timestamps are missing
        events.append(TimelineEvent(
            timestamp_ms=ts,
            kind="console",
            label=str(message.get("type") or "log"),
            payload={"text": message.get("text"), "location": message.get("location")},
        ))
    return events


def from_responses(responses: Iterable[Dict[str, Any]]) -> List[TimelineEvent]:
    events: List[TimelineEvent] = []
    for index, response in enumerate(responses):
        ts = _coerce_timestamp(_first_present(response, "timestamp_ms", "ts"))
        if ts is None:
            ts = float(index)
        events.append(TimelineEvent(
            timestamp_ms=ts,
            kind="response",
            label=f"{response.get('method', 'GET')} {response.get('status', '?')}",
            payload={
                "url": response.get("url"),
                "status": response.get("status"),
                "ok": response.get("ok"),
            },
        ))
    return events


def merge(*event_lists: Iterable[TimelineEvent]) -> List[TimelineEvent]:
    """Concatenate event lists and sort by timestamp ascending (stable)."""
    merged: List[TimelineEvent] = []
    for events in event_lists:
        merged.extend(events)
    merged.sort(key=lambda evt: evt.timestamp_ms)
    return merged


def to_dicts(events: Iterable[TimelineEvent]) -> List[Dict[str, Any]]:
    return [
        {
            "timestamp_ms": e.timestamp_ms,
            "kind": e.kind,
            "label": e.label,
            "payload": e.payload,
        }
        for e in events
    ]


def build(
    spans: Optional[Iterable[Dict[str, Any]]] = None,
    console: Optional[Iterable[Dict[str, Any]]] = None,
    responses: Optional[Iterable[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Top-level helper: take three optional sources, return one ordered list."""
    return to_dicts(merge(
        from_spans(spans or []),
        from_console(console or []),
        from_responses(responses or []),
    ))
