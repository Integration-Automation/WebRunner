"""
HTTP/3 WebTransport stream assertions — 對齊 ``websocket_assert`` 與
``sse_assert`` 的設計,讓三種雙向通訊測試都長一樣。

WebTransport 同時提供 datagrams + 雙向 / 單向 streams,所以模型比 WS 多
一層:每筆事件除了 direction(sent / received),還有 channel
('datagram' / 'stream') 與 stream_id。

Recorder is fed by any source that knows how to listen (CDP
``Network.dataReceived`` filtered by WT session, Playwright route, or a
custom JS shim posted via ``window.postMessage``).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Pattern, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebTransportAssertError(WebRunnerException):
    """Raised on malformed payload / direction / channel or failed assertion."""


SENT = "sent"
RECEIVED = "received"
_DIRECTIONS = {SENT, RECEIVED}

DATAGRAM = "datagram"
STREAM = "stream"
_CHANNELS = {DATAGRAM, STREAM}


# ---------- model -------------------------------------------------------

@dataclass
class WtFrame:
    """One WebTransport datagram or stream chunk."""

    direction: str
    channel: str
    payload: bytes
    stream_id: Optional[int] = None
    fin: bool = False
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.direction not in _DIRECTIONS:
            raise WebTransportAssertError(
                f"direction must be one of {_DIRECTIONS}, got {self.direction!r}"
            )
        if self.channel not in _CHANNELS:
            raise WebTransportAssertError(
                f"channel must be one of {_CHANNELS}, got {self.channel!r}"
            )
        if not isinstance(self.payload, (bytes, bytearray)):
            raise WebTransportAssertError(
                f"payload must be bytes, got {type(self.payload).__name__}"
            )
        if self.channel == STREAM and self.stream_id is None:
            raise WebTransportAssertError("stream frames require stream_id")

    def as_text(self, encoding: str = "utf-8") -> str:
        """Decode payload as text; replacement chars on bad bytes."""
        return bytes(self.payload).decode(encoding, errors="replace")

    def as_json(self) -> Any:
        try:
            return json.loads(self.as_text())
        except ValueError as error:
            raise WebTransportAssertError(
                f"frame payload is not JSON ({error}): {self.payload[:40]!r}"
            ) from error

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["payload_b64"] = bytes(self.payload).hex()
        out.pop("payload", None)
        return out


# ---------- recorder ----------------------------------------------------

class WtFrameRecorder:
    """In-memory recorder for one WT session."""

    def __init__(self) -> None:
        self._frames: List[WtFrame] = []

    def __len__(self) -> int:
        return len(self._frames)

    def record(self, frame: WtFrame) -> None:
        if not isinstance(frame, WtFrame):
            raise WebTransportAssertError(
                f"record() expects WtFrame, got {type(frame).__name__}"
            )
        self._frames.append(frame)

    def record_sent_datagram(self, payload: bytes) -> None:
        self.record(WtFrame(direction=SENT, channel=DATAGRAM, payload=payload))

    def record_received_datagram(self, payload: bytes) -> None:
        self.record(WtFrame(direction=RECEIVED, channel=DATAGRAM, payload=payload))

    def record_stream_chunk(
        self,
        direction: str,
        stream_id: int,
        payload: bytes,
        *,
        fin: bool = False,
    ) -> None:
        self.record(WtFrame(
            direction=direction, channel=STREAM,
            payload=payload, stream_id=stream_id, fin=fin,
        ))

    def clear(self) -> None:
        self._frames.clear()

    def frames(
        self,
        *,
        direction: Optional[str] = None,
        channel: Optional[str] = None,
        stream_id: Optional[int] = None,
    ) -> List[WtFrame]:
        if direction is not None and direction not in _DIRECTIONS:
            raise WebTransportAssertError(f"unknown direction {direction!r}")
        if channel is not None and channel not in _CHANNELS:
            raise WebTransportAssertError(f"unknown channel {channel!r}")
        out: List[WtFrame] = []
        for frame in self._frames:
            if direction is not None and frame.direction != direction:
                continue
            if channel is not None and frame.channel != channel:
                continue
            if stream_id is not None and frame.stream_id != stream_id:
                continue
            out.append(frame)
        return out

    def stream_ids(self) -> List[int]:
        return sorted({f.stream_id for f in self._frames if f.stream_id is not None})


# ---------- assertions --------------------------------------------------

def assert_datagram_count(
    recorder: WtFrameRecorder,
    *,
    direction: Optional[str] = None,
    minimum: int = 0,
    maximum: Optional[int] = None,
) -> int:
    """Assert ``minimum <= datagram_count <= maximum``."""
    if minimum < 0:
        raise WebTransportAssertError("minimum must be >= 0")
    if maximum is not None and maximum < minimum:
        raise WebTransportAssertError("maximum must be >= minimum")
    count = len(recorder.frames(direction=direction, channel=DATAGRAM))
    if count < minimum or (maximum is not None and count > maximum):
        raise WebTransportAssertError(
            f"datagram count out of range: got {count}, want "
            f"[{minimum}, {maximum if maximum is not None else 'inf'}]"
        )
    return count


def assert_stream_complete(
    recorder: WtFrameRecorder,
    stream_id: int,
    *,
    direction: str = RECEIVED,
) -> bytes:
    """Assert a stream ended with FIN; return the concatenated payload."""
    if direction not in _DIRECTIONS:
        raise WebTransportAssertError(f"unknown direction {direction!r}")
    chunks = recorder.frames(
        direction=direction, channel=STREAM, stream_id=stream_id,
    )
    if not chunks:
        raise WebTransportAssertError(
            f"no {direction} stream chunks recorded for stream_id={stream_id}"
        )
    if not chunks[-1].fin:
        raise WebTransportAssertError(
            f"stream {stream_id} ({direction}) did not end with fin"
        )
    return b"".join(bytes(c.payload) for c in chunks)


def assert_payload_contains(
    recorder: WtFrameRecorder,
    needle: bytes,
    *,
    direction: Optional[str] = None,
    channel: Optional[str] = None,
) -> WtFrame:
    """Assert at least one frame's payload contains ``needle``."""
    if not isinstance(needle, (bytes, bytearray)) or not needle:
        raise WebTransportAssertError("needle must be non-empty bytes")
    for frame in recorder.frames(direction=direction, channel=channel):
        if bytes(needle) in bytes(frame.payload):
            return frame
    raise WebTransportAssertError(
        f"no frame contained {needle[:20]!r} "
        f"(direction={direction}, channel={channel})"
    )


def assert_json_shape(
    recorder: WtFrameRecorder,
    required_keys: Sequence[str],
    *,
    direction: Optional[str] = RECEIVED,
) -> WtFrame:
    """Assert a JSON-decodable frame whose top-level dict has every key."""
    if not required_keys:
        raise WebTransportAssertError("required_keys must be non-empty")
    wanted = set(required_keys)
    for frame in recorder.frames(direction=direction):
        try:
            obj = frame.as_json()
        except WebTransportAssertError:
            continue
        if isinstance(obj, dict) and wanted.issubset(obj.keys()):
            return frame
    raise WebTransportAssertError(
        f"no {direction} frame had keys {sorted(wanted)}"
    )


def to_json(frames: Iterable[WtFrame]) -> str:
    """Serialise frames as a JSON array (payload as hex)."""
    return json.dumps([f.to_dict() for f in frames], ensure_ascii=False, indent=2)
