"""
視窗座標換算 / Map a point in the page to the screen pixel the mouse takes.

Browsers report the window's position and outer size (``screenX/Y``, ``outerWidth/Height``)
in screen pixels, and element rectangles and the viewport (``innerWidth/Height``) in CSS
pixels. With page zoom ``z`` one CSS pixel is ``z`` screen pixels, and
``devicePixelRatio`` is ``scale * z``, where ``scale`` is the operating system's display
scale for the browser's monitor: mouse pixels per screen pixel for a DPI-aware process
such as AutoControl.

The window frame is taken to be as thick at the bottom as at each side, which holds for
the desktop browsers on Windows, macOS and the common Linux desktops: the viewport starts
``(outerWidth - innerWidth * z) / 2`` in from the window's left edge and
``outerHeight - innerHeight * z - that`` down from its top edge.
"""
from __future__ import annotations

from typing import Mapping

from je_web_runner.utils.autocontrol_bridge.bridge import AutoControlBridgeError

# Collected in one call, after scrolling the element to the middle of the viewport.
METRICS_SCRIPT = """
const element = arguments[0];
element.scrollIntoView({block: 'center', inline: 'center'});
const rect = element.getBoundingClientRect();
return {left: rect.left, top: rect.top, width: rect.width, height: rect.height,
        screenX: window.screenX, screenY: window.screenY,
        outerWidth: window.outerWidth, outerHeight: window.outerHeight,
        innerWidth: window.innerWidth, innerHeight: window.innerHeight,
        devicePixelRatio: window.devicePixelRatio};
"""

_KEYS = ("left", "top", "width", "height", "screenX", "screenY",
         "outerWidth", "outerHeight", "innerWidth", "innerHeight", "devicePixelRatio")


class ScreenMappingError(AutoControlBridgeError):
    """The metrics cannot place the element on the screen."""


def _checked(metrics: Mapping[str, float]) -> dict[str, float]:
    missing = [key for key in _KEYS if not isinstance(metrics.get(key), (int, float))]
    if missing:
        raise ScreenMappingError(f"window metrics lack {missing}")
    values = {key: float(metrics[key]) for key in _KEYS}
    if values["width"] <= 0 or values["height"] <= 0:
        raise ScreenMappingError("the element has no size on the page")
    if values["devicePixelRatio"] <= 0:
        raise ScreenMappingError("devicePixelRatio must be positive")
    return values


def element_center_on_screen(metrics: Mapping[str, float], scale: float | None = None) -> tuple[int, int]:
    """
    元素中心的螢幕座標（滑鼠用的像素）
    The mouse coordinates of the centre of the element described by ``metrics`` (the
    result of :data:`METRICS_SCRIPT`). ``scale`` is the operating system's display scale
    of the browser's monitor (1.25 for 125 %); None takes ``devicePixelRatio``, which is
    right when the page is at 100 % zoom. Raises :class:`ScreenMappingError` when the
    element has no size or its centre is outside the viewport.
    """
    values = _checked(metrics)
    display_scale = float(scale) if scale else values["devicePixelRatio"]
    if display_scale <= 0:
        raise ScreenMappingError("scale must be positive")
    zoom = values["devicePixelRatio"] / display_scale
    center_x = values["left"] + values["width"] / 2
    center_y = values["top"] + values["height"] / 2
    if not (0 <= center_x < values["innerWidth"] and 0 <= center_y < values["innerHeight"]):
        raise ScreenMappingError(f"the element's centre ({center_x:.0f}, {center_y:.0f}) is outside the viewport")
    side = max(0.0, (values["outerWidth"] - values["innerWidth"] * zoom) / 2)
    top = max(0.0, values["outerHeight"] - values["innerHeight"] * zoom - side)
    screen_x = values["screenX"] + side + center_x * zoom
    screen_y = values["screenY"] + top + center_y * zoom
    return round(screen_x * display_scale), round(screen_y * display_scale)
