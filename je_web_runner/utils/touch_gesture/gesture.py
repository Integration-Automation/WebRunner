"""
Touch gesture sequence builder + assertion helpers.

Builds CDP-compatible ``Input.dispatchTouchEvent`` sequences for the
four common multi-touch gestures (tap, swipe, pinch, long-press) and
parses recorded ``TouchEvent`` payloads back into Python ``Gesture``
objects for assertion.

The dispatcher itself is delegated via a ``Caller`` Protocol — we don't
import any specific WebDriver/CDP client.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException


class TouchGestureError(WebRunnerException):
    """Raised on malformed input or assertion failure."""


class Phase(str, Enum):
    START = "touchStart"
    MOVE = "touchMove"
    END = "touchEnd"
    CANCEL = "touchCancel"


@dataclass
class TouchPoint:
    x: float
    y: float
    id: int = 0
    radius_x: float = 5
    radius_y: float = 5
    force: float = 1.0


@dataclass
class TouchFrame:
    """One CDP ``Input.dispatchTouchEvent`` payload."""

    type: Phase
    points: List[TouchPoint] = field(default_factory=list)

    def to_cdp(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "touchPoints": [
                {"x": p.x, "y": p.y, "id": p.id,
                 "radiusX": p.radius_x, "radiusY": p.radius_y,
                 "force": p.force}
                for p in self.points
            ],
        }


def _validate_point(x: float, y: float) -> None:
    if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
        raise TouchGestureError("x/y must be numbers")


def tap(x: float, y: float) -> List[TouchFrame]:
    _validate_point(x, y)
    return [
        TouchFrame(type=Phase.START, points=[TouchPoint(x=x, y=y, id=1)]),
        TouchFrame(type=Phase.END, points=[]),
    ]


def long_press(x: float, y: float, *, hold_ms: int = 800) -> List[TouchFrame]:
    if hold_ms < 500:
        raise TouchGestureError(
            "hold_ms must be >= 500 to count as long-press on most platforms"
        )
    _validate_point(x, y)
    # CDP needs three frames: start, optional dwell with no move (we emit a
    # zero-distance move so the consumer can time it), end.
    return [
        TouchFrame(type=Phase.START, points=[TouchPoint(x=x, y=y, id=1)]),
        TouchFrame(type=Phase.MOVE, points=[TouchPoint(x=x, y=y, id=1)]),
        TouchFrame(type=Phase.END, points=[]),
    ]


def swipe(
    start: Tuple[float, float], end: Tuple[float, float],
    *, steps: int = 8,
) -> List[TouchFrame]:
    if steps < 2:
        raise TouchGestureError("steps must be >= 2 for a credible swipe")
    sx, sy = start
    ex, ey = end
    _validate_point(sx, sy)
    _validate_point(ex, ey)
    frames: List[TouchFrame] = [
        TouchFrame(type=Phase.START, points=[TouchPoint(x=sx, y=sy, id=1)]),
    ]
    for i in range(1, steps):
        t = i / steps
        frames.append(TouchFrame(type=Phase.MOVE, points=[
            TouchPoint(x=sx + (ex - sx) * t, y=sy + (ey - sy) * t, id=1),
        ]))
    frames.append(TouchFrame(type=Phase.END, points=[]))
    return frames


def pinch(
    centre: Tuple[float, float], *, start_radius: float, end_radius: float,
    steps: int = 8,
) -> List[TouchFrame]:
    """Two-finger pinch: spread if end > start, pinch if end < start."""
    if start_radius <= 0 or end_radius <= 0:
        raise TouchGestureError("radii must be positive")
    if steps < 2:
        raise TouchGestureError("steps must be >= 2")
    cx, cy = centre
    _validate_point(cx, cy)
    def at(r: float) -> Tuple[TouchPoint, TouchPoint]:
        return (TouchPoint(x=cx - r, y=cy, id=1),
                TouchPoint(x=cx + r, y=cy, id=2))
    frames = [TouchFrame(type=Phase.START, points=list(at(start_radius)))]
    for i in range(1, steps):
        t = i / steps
        r = start_radius + (end_radius - start_radius) * t
        frames.append(TouchFrame(type=Phase.MOVE, points=list(at(r))))
    frames.append(TouchFrame(type=Phase.END, points=[]))
    return frames


# -------------- recorded event parsing & assertions ------------------


@dataclass
class RecordedTouch:
    type: str        # "touchstart" | "touchmove" | "touchend" | "touchcancel"
    touch_count: int = 0
    target: str = ""


def parse_touch_events(payload: Any) -> List[RecordedTouch]:
    if not isinstance(payload, list):
        raise TouchGestureError("payload must be a list")
    out: List[RecordedTouch] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        out.append(RecordedTouch(
            type=str(raw.get("type") or ""),
            touch_count=int(raw.get("touchCount") or 0),
            target=str(raw.get("target") or ""),
        ))
    return out


def assert_received(
    events: Iterable[RecordedTouch], *, event_type: str,
) -> None:
    if not any(e.type == event_type for e in events):
        raise TouchGestureError(
            f"page never received {event_type!r} event"
        )


def assert_two_finger(events: Iterable[RecordedTouch]) -> None:
    if not any(e.touch_count >= 2 for e in events):
        raise TouchGestureError(
            "no touch event with >=2 simultaneous fingers"
        )


def gesture_distance_px(frames: Sequence[TouchFrame]) -> float:
    """Approx total finger travel for one-finger gestures."""
    points = [f.points[0] for f in frames if f.points]
    if len(points) < 2:
        return 0.0
    return sum(math.hypot(b.x - a.x, b.y - a.y)
               for a, b in zip(points, points[1:], strict=False))
