"""
gRPC streaming assertion helpers.

Models the four gRPC modes (unary / server-stream / client-stream / bidi)
and provides assertions for a captured ``StreamRecord`` (the transport
callable returns this record so we stay client-library agnostic):

* Frame count is within a bound.
* Frames arrive in the expected order.
* No frame exceeded a per-message size budget.
* Stream terminated with the expected status code.
* No deadline-exceeded inside the stream.
* Half-close happened before the server's final message (bidi).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class GrpcStreamingAssertError(WebRunnerException):
    """Raised when a streaming invariant is violated."""


class Mode(str, Enum):
    UNARY = "unary"
    SERVER_STREAM = "server_stream"
    CLIENT_STREAM = "client_stream"
    BIDI = "bidi"


class StatusCode(str, Enum):
    OK = "OK"
    CANCELLED = "CANCELLED"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    INTERNAL = "INTERNAL"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"


@dataclass
class StreamFrame:
    payload_size: int = 0
    body: dict[str, Any] = field(default_factory=dict)
    ts_ms: float = 0
    direction: str = "in"   # "in" (server → client) | "out"


@dataclass
class StreamRecord:
    method: str
    mode: Mode
    frames: list[StreamFrame] = field(default_factory=list)
    status: StatusCode = StatusCode.OK
    half_closed_ts_ms: float | None = None
    duration_ms: float = 0

    @property
    def inbound(self) -> list[StreamFrame]:
        return [f for f in self.frames if f.direction == "in"]

    @property
    def outbound(self) -> list[StreamFrame]:
        return [f for f in self.frames if f.direction == "out"]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "mode": self.mode.value,
            "status": self.status.value,
        }


def parse_record(payload: Any) -> StreamRecord:
    if not isinstance(payload, dict):
        raise GrpcStreamingAssertError("payload must be a dict")
    try:
        mode = Mode(payload.get("mode", Mode.UNARY.value))
    except ValueError as exc:
        raise GrpcStreamingAssertError(
            f"unknown mode {payload.get('mode')!r}"
        ) from exc
    try:
        status = StatusCode(payload.get("status", StatusCode.OK.value))
    except ValueError as exc:
        raise GrpcStreamingAssertError(
            f"unknown status {payload.get('status')!r}"
        ) from exc
    frames = []
    for raw in payload.get("frames") or []:
        if not isinstance(raw, dict):
            continue
        frames.append(StreamFrame(
            payload_size=int(raw.get("payload_size") or 0),
            body=raw.get("body") or {},
            ts_ms=float(raw.get("ts_ms") or 0),
            direction=str(raw.get("direction") or "in"),
        ))
    return StreamRecord(
        method=str(payload.get("method") or ""),
        mode=mode,
        frames=frames,
        status=status,
        half_closed_ts_ms=payload.get("half_closed_ts_ms"),
        duration_ms=float(payload.get("duration_ms") or 0),
    )


def assert_status(record: StreamRecord, expected: StatusCode) -> None:
    if record.status != expected:
        raise GrpcStreamingAssertError(
            f"status {record.status.value} != expected {expected.value}"
        )


def assert_frame_count_between(
    record: StreamRecord, *, min_count: int, max_count: int,
    direction: str = "in",
) -> None:
    if min_count < 0 or max_count < min_count:
        raise GrpcStreamingAssertError("invalid bounds")
    frames = record.inbound if direction == "in" else record.outbound
    if not (min_count <= len(frames) <= max_count):
        raise GrpcStreamingAssertError(
            f"frame count {len(frames)} not in [{min_count}, {max_count}]"
        )


def assert_max_frame_size(record: StreamRecord, *, max_bytes: int) -> None:
    if max_bytes <= 0:
        raise GrpcStreamingAssertError("max_bytes must be positive")
    big = [f for f in record.frames if f.payload_size > max_bytes]
    if big:
        worst = max(big, key=lambda f: f.payload_size)
        raise GrpcStreamingAssertError(
            f"{len(big)} frame(s) exceed {max_bytes}B "
            f"(worst={worst.payload_size}B)"
        )


def assert_frames_in_order(
    record: StreamRecord, *, key: str, expected: Sequence[Any],
    direction: str = "in",
) -> None:
    frames = record.inbound if direction == "in" else record.outbound
    actual = [f.body.get(key) for f in frames]
    if actual != list(expected):
        raise GrpcStreamingAssertError(
            f"order mismatch: expected {list(expected)}, got {actual}"
        )


def assert_no_deadline_exceeded(record: StreamRecord) -> None:
    if record.status == StatusCode.DEADLINE_EXCEEDED:
        raise GrpcStreamingAssertError(
            f"stream {record.method!r} hit DEADLINE_EXCEEDED"
        )


def assert_half_close_before_final(record: StreamRecord) -> None:
    """For bidi streams: client must half-close before server's last frame."""
    if record.mode != Mode.BIDI:
        raise GrpcStreamingAssertError(
            "assert_half_close_before_final only applies to bidi mode"
        )
    if record.half_closed_ts_ms is None:
        raise GrpcStreamingAssertError("client never half-closed")
    if not record.inbound:
        return
    last_in = max(f.ts_ms for f in record.inbound)
    if record.half_closed_ts_ms > last_in:
        raise GrpcStreamingAssertError(
            f"half-close at {record.half_closed_ts_ms}ms is AFTER "
            f"last server frame at {last_in}ms"
        )
