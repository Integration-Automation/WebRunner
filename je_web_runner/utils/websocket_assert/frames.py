"""
記錄 WebSocket frames + 對 frame pattern / count / message shape 做斷言。
The recorder is a tiny event sink: any source that knows how to listen to
WebSocket frames (CDP ``Network.webSocketFrame*``, a Selenium 4 BiDi
listener, a Playwright callback, or a unit-test fixture) pushes
:class:`WsFrame` records into :class:`WsFrameRecorder`.

The assertion helpers then work purely off the recorded list — they have
no transport coupling, so the same suite of asserts works for any driver.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Pattern, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class WebSocketAssertError(WebRunnerException):
    """Raised on malformed input, JSON decode failure, or failed assertion."""


SENT = "sent"
RECEIVED = "received"
_DIRECTIONS = {SENT, RECEIVED}


# ---------- frame model -------------------------------------------------

@dataclass
class WsFrame:
    """One WebSocket message frame."""

    direction: str
    url: str
    payload: str
    timestamp: float = field(default_factory=time.time)
    opcode: int = 1  # 1=text, 2=binary by default

    def __post_init__(self) -> None:
        if self.direction not in _DIRECTIONS:
            raise WebSocketAssertError(
                f"direction must be 'sent' or 'received', got {self.direction!r}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def as_json(self) -> Any:
        """Decode :attr:`payload` as JSON; raise if undecodable."""
        try:
            return json.loads(self.payload)
        except ValueError as error:
            raise WebSocketAssertError(
                f"frame payload is not JSON ({error}): {self.payload[:80]!r}"
            ) from error


# ---------- recorder ----------------------------------------------------

class WsFrameRecorder:
    """Thread-unsafe in-memory recorder. Wrap with a Lock if shared."""

    def __init__(self) -> None:
        self._frames: List[WsFrame] = []

    def __len__(self) -> int:
        return len(self._frames)

    def record(self, frame: WsFrame) -> None:
        if not isinstance(frame, WsFrame):
            raise WebSocketAssertError(
                f"record() expects WsFrame, got {type(frame).__name__}"
            )
        self._frames.append(frame)

    def record_sent(self, url: str, payload: str, *, opcode: int = 1) -> None:
        self.record(WsFrame(direction=SENT, url=url, payload=payload, opcode=opcode))

    def record_received(self, url: str, payload: str, *, opcode: int = 1) -> None:
        self.record(WsFrame(direction=RECEIVED, url=url, payload=payload, opcode=opcode))

    def clear(self) -> None:
        self._frames.clear()

    def frames(
        self,
        *,
        direction: Optional[str] = None,
        url_match: Optional[Union[str, Pattern[str]]] = None,
    ) -> List[WsFrame]:
        """Return a filtered snapshot list (the recorder is unmodified)."""
        if direction is not None and direction not in _DIRECTIONS:
            raise WebSocketAssertError(f"unknown direction {direction!r}")
        url_pattern = _coerce_pattern(url_match)
        out = []
        for frame in self._frames:
            if direction is not None and frame.direction != direction:
                continue
            if url_pattern is not None and not url_pattern.search(frame.url):
                continue
            out.append(frame)
        return out


def _coerce_pattern(value: Optional[Union[str, Pattern[str]]]) -> Optional[Pattern[str]]:
    if value is None:
        return None
    if hasattr(value, "search"):
        return value  # already a compiled pattern
    return re.compile(str(value))


# ---------- assertions --------------------------------------------------

def assert_frame_count(
    recorder: WsFrameRecorder,
    *,
    direction: Optional[str] = None,
    url_match: Optional[Union[str, Pattern[str]]] = None,
    minimum: int = 0,
    maximum: Optional[int] = None,
) -> int:
    """Assert ``minimum <= count <= maximum`` for the filtered frames."""
    if minimum < 0:
        raise WebSocketAssertError("minimum must be >= 0")
    if maximum is not None and maximum < minimum:
        raise WebSocketAssertError("maximum must be >= minimum")
    matching = recorder.frames(direction=direction, url_match=url_match)
    count = len(matching)
    if count < minimum or (maximum is not None and count > maximum):
        raise WebSocketAssertError(
            f"frame count out of range: got {count}, want "
            f"[{minimum}, {maximum if maximum is not None else 'inf'}] "
            f"(direction={direction}, url_match={url_match})"
        )
    return count


def assert_frame_received(
    recorder: WsFrameRecorder,
    predicate: Callable[[WsFrame], bool],
    *,
    description: str = "frame predicate",
) -> WsFrame:
    """Assert that at least one received frame matches ``predicate``."""
    for frame in recorder.frames(direction=RECEIVED):
        try:
            if predicate(frame):
                return frame
        except Exception as error:
            web_runner_logger.warning(f"ws predicate raised: {error!r}")
    raise WebSocketAssertError(f"no received frame matched: {description}")


def assert_payload_contains(
    recorder: WsFrameRecorder,
    needle: str,
    *,
    direction: Optional[str] = None,
) -> WsFrame:
    """Assert a frame whose text payload contains ``needle``."""
    if not isinstance(needle, str) or not needle:
        raise WebSocketAssertError("needle must be a non-empty string")
    for frame in recorder.frames(direction=direction):
        if needle in frame.payload:
            return frame
    raise WebSocketAssertError(
        f"no frame contained {needle!r} (direction={direction})"
    )


def assert_json_shape(
    recorder: WsFrameRecorder,
    required_keys: Sequence[str],
    *,
    direction: Optional[str] = RECEIVED,
) -> WsFrame:
    """Assert a JSON frame whose top-level object has every ``required_keys`` key."""
    if not required_keys:
        raise WebSocketAssertError("required_keys must be a non-empty sequence")
    wanted = set(required_keys)
    for frame in recorder.frames(direction=direction):
        try:
            obj = frame.as_json()
        except WebSocketAssertError:
            continue
        if isinstance(obj, dict) and wanted.issubset(obj.keys()):
            return frame
    raise WebSocketAssertError(
        f"no {direction} frame had keys {sorted(wanted)}"
    )


def assert_pubsub_pattern(
    recorder: WsFrameRecorder,
    *,
    subscribe_matcher: Callable[[WsFrame], bool],
    publish_matcher: Callable[[WsFrame], bool],
) -> None:
    """
    斷言客戶端先送 subscribe,後續才收到 publish。
    Walk frames in record order. A ``sent`` frame matching
    ``subscribe_matcher`` must appear before any ``received`` frame
    matching ``publish_matcher``.
    """
    seen_subscribe = False
    for frame in recorder.frames():
        if frame.direction == SENT and subscribe_matcher(frame):
            seen_subscribe = True
            continue
        if frame.direction == RECEIVED and publish_matcher(frame):
            if not seen_subscribe:
                raise WebSocketAssertError(
                    "received a matching publish before any matching subscribe"
                )
            return
    raise WebSocketAssertError(
        "did not observe a subscribe→publish pair matching the given matchers"
    )


# ---------- export ------------------------------------------------------

def to_json(frames: Iterable[WsFrame]) -> str:
    """Serialise frames as a JSON array for failure-bundle attachment."""
    return json.dumps([f.to_dict() for f in frames], ensure_ascii=False, indent=2)
