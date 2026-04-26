"""
Appium 手勢 helper：把常見的 swipe / pinch / scroll / long-press 包成宣告式 API。
Mobile gesture helpers for Appium drivers. Each function emits a W3C
Actions sequence so it stays compatible with both UiAutomator2 (Android)
and XCUITest (iOS) without per-platform branching.

The driver is required to expose either ``execute_script`` (for the
``mobile:`` named-gesture extensions) or ``perform_actions`` (for raw
W3C input). The helpers prefer the named extension when present and
fall back to W3C otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException


class AppiumGestureError(WebRunnerException):
    """Raised when the driver cannot execute the gesture."""


_DIRECTIONS = {"up", "down", "left", "right"}


@dataclass(frozen=True)
class Point:
    x: int
    y: int


def _execute_named_gesture(
    driver: Any,
    name: str,
    args: Dict[str, Any],
) -> bool:
    """Try the ``mobile:<name>`` extension via ``execute_script``."""
    if not hasattr(driver, "execute_script"):
        return False
    try:
        driver.execute_script(f"mobile: {name}", args)
        return True
    except Exception:  # pylint: disable=broad-except
        return False


def _w3c_pointer_path(actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Wrap a list of pointer actions into the W3C Actions envelope."""
    return [{
        "type": "pointer",
        "id": "finger1",
        "parameters": {"pointerType": "touch"},
        "actions": actions,
    }]


def _perform_w3c(driver: Any, actions: List[Dict[str, Any]]) -> None:
    if not hasattr(driver, "perform_actions"):
        raise AppiumGestureError(
            "driver lacks perform_actions and the mobile: gesture extension"
        )
    driver.perform_actions(actions)


def swipe(
    driver: Any,
    start: Point,
    end: Point,
    duration_ms: int = 250,
) -> None:
    """Swipe from ``start`` to ``end`` over ``duration_ms`` milliseconds."""
    if duration_ms <= 0:
        raise AppiumGestureError("duration_ms must be > 0")
    if _execute_named_gesture(driver, "swipeGesture", {
        "left": min(start.x, end.x),
        "top": min(start.y, end.y),
        "width": abs(end.x - start.x) + 1,
        "height": abs(end.y - start.y) + 1,
        "direction": _direction_for(start, end),
        "percent": 0.9,
    }):
        return
    _perform_w3c(driver, _w3c_pointer_path([
        {"type": "pointerMove", "duration": 0, "x": start.x, "y": start.y},
        {"type": "pointerDown", "button": 0},
        {"type": "pointerMove", "duration": duration_ms,
         "x": end.x, "y": end.y},
        {"type": "pointerUp", "button": 0},
    ]))


def _direction_for(start: Point, end: Point) -> str:
    if abs(end.x - start.x) >= abs(end.y - start.y):
        return "left" if end.x < start.x else "right"
    return "up" if end.y < start.y else "down"


def scroll(
    driver: Any,
    direction: str,
    rect: Optional[Tuple[int, int, int, int]] = None,
    percent: float = 0.7,
) -> None:
    """Scroll ``direction`` (``up`` / ``down`` / ``left`` / ``right``)."""
    if direction not in _DIRECTIONS:
        raise AppiumGestureError(
            f"direction must be one of {_DIRECTIONS}, got {direction!r}"
        )
    if not 0 < percent <= 1:
        raise AppiumGestureError("percent must be in (0, 1]")
    args: Dict[str, Any] = {"direction": direction, "percent": percent}
    if rect is not None:
        left, top, width, height = rect
        args.update({"left": left, "top": top, "width": width, "height": height})
    if _execute_named_gesture(driver, "scrollGesture", args):
        return
    # Fallback: synthesize a swipe in the centre of the supplied rect.
    centre = _centre(rect or (0, 0, 600, 800))
    delta = int(percent * 400)
    if direction == "up":
        end = Point(centre.x, centre.y - delta)
    elif direction == "down":
        end = Point(centre.x, centre.y + delta)
    elif direction == "left":
        end = Point(centre.x - delta, centre.y)
    else:
        end = Point(centre.x + delta, centre.y)
    swipe(driver, centre, end)


def _centre(rect: Tuple[int, int, int, int]) -> Point:
    left, top, width, height = rect
    return Point(left + width // 2, top + height // 2)


def long_press(
    driver: Any,
    point: Point,
    duration_ms: int = 1000,
) -> None:
    """Hold the finger at ``point`` for ``duration_ms``."""
    if duration_ms <= 0:
        raise AppiumGestureError("duration_ms must be > 0")
    if _execute_named_gesture(driver, "longClickGesture", {
        "x": point.x, "y": point.y, "duration": duration_ms,
    }):
        return
    _perform_w3c(driver, _w3c_pointer_path([
        {"type": "pointerMove", "duration": 0, "x": point.x, "y": point.y},
        {"type": "pointerDown", "button": 0},
        {"type": "pause", "duration": duration_ms},
        {"type": "pointerUp", "button": 0},
    ]))


def pinch(
    driver: Any,
    rect: Tuple[int, int, int, int],
    scale: float = 0.5,
    speed: int = 1500,
) -> None:
    """Pinch the area inside ``rect`` to ``scale`` (``< 1`` = zoom out, ``> 1`` = zoom in)."""
    if scale <= 0:
        raise AppiumGestureError("scale must be > 0")
    name = "pinchOpenGesture" if scale > 1 else "pinchCloseGesture"
    left, top, width, height = rect
    if _execute_named_gesture(driver, name, {
        "left": left, "top": top, "width": width, "height": height,
        "percent": min(0.99, abs(scale - 1)),
        "speed": speed,
    }):
        return
    centre = _centre(rect)
    delta = int(min(width, height) * 0.4)
    raw_a = [
        {"type": "pointer", "id": "finger1",
         "parameters": {"pointerType": "touch"},
         "actions": [
            {"type": "pointerMove", "duration": 0,
             "x": centre.x - delta, "y": centre.y - delta},
            {"type": "pointerDown", "button": 0},
            {"type": "pointerMove", "duration": speed,
             "x": centre.x - (delta // 2 if scale > 1 else delta * 2),
             "y": centre.y - (delta // 2 if scale > 1 else delta * 2)},
            {"type": "pointerUp", "button": 0},
         ]},
        {"type": "pointer", "id": "finger2",
         "parameters": {"pointerType": "touch"},
         "actions": [
            {"type": "pointerMove", "duration": 0,
             "x": centre.x + delta, "y": centre.y + delta},
            {"type": "pointerDown", "button": 0},
            {"type": "pointerMove", "duration": speed,
             "x": centre.x + (delta // 2 if scale > 1 else delta * 2),
             "y": centre.y + (delta // 2 if scale > 1 else delta * 2)},
            {"type": "pointerUp", "button": 0},
         ]},
    ]
    _perform_w3c(driver, raw_a)


def double_tap(driver: Any, point: Point, gap_ms: int = 100) -> None:
    """Two quick taps at ``point``."""
    if gap_ms <= 0:
        raise AppiumGestureError("gap_ms must be > 0")
    if _execute_named_gesture(driver, "doubleClickGesture", {
        "x": point.x, "y": point.y,
    }):
        return
    _perform_w3c(driver, _w3c_pointer_path([
        {"type": "pointerMove", "duration": 0, "x": point.x, "y": point.y},
        {"type": "pointerDown", "button": 0},
        {"type": "pointerUp", "button": 0},
        {"type": "pause", "duration": gap_ms},
        {"type": "pointerDown", "button": 0},
        {"type": "pointerUp", "button": 0},
    ]))
