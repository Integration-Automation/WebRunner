"""
Virtual (on-screen) keyboard show/hide impact assertions.

When iOS / Android shows the soft keyboard, the visual viewport shrinks
and the layout viewport may or may not. Common bugs:

* Sticky-bottom CTA gets hidden behind the keyboard.
* Modal scrolls *under* the keyboard instead of resizing.
* ``window.visualViewport`` listener never fires (page assumes resize
  event only).

This module ships the harvest JS to read ``visualViewport`` before/after
the keyboard appears, plus assertions to verify the layout reacted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict

from je_web_runner.utils.exception.exceptions import WebRunnerException


class VirtualKeyboardError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


HARVEST_SCRIPT = r"""
(function () {
  const vv = window.visualViewport;
  const cs = getComputedStyle(document.documentElement);
  return {
    viewport_width: vv ? vv.width : window.innerWidth,
    viewport_height: vv ? vv.height : window.innerHeight,
    scale: vv ? vv.scale : 1,
    offset_top: vv ? vv.offsetTop : 0,
    keyboard_inset: cs.getPropertyValue('--keyboard-inset-height') || '',
  };
})();
"""


@dataclass
class ViewportSnapshot:
    viewport_width: float = 0
    viewport_height: float = 0
    scale: float = 1
    offset_top: float = 0
    keyboard_inset: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_snapshot(payload: Any) -> ViewportSnapshot:
    if not isinstance(payload, dict):
        raise VirtualKeyboardError("payload must be a dict")
    return ViewportSnapshot(
        viewport_width=float(payload.get("viewport_width") or 0),
        viewport_height=float(payload.get("viewport_height") or 0),
        scale=float(payload.get("scale") or 1),
        offset_top=float(payload.get("offset_top") or 0),
        keyboard_inset=str(payload.get("keyboard_inset") or ""),
    )


def assert_keyboard_shrunk(
    *, before: ViewportSnapshot, after: ViewportSnapshot,
    min_height_delta_px: float = 100,
) -> None:
    """``after`` must be at least ``min_height_delta_px`` shorter."""
    if min_height_delta_px <= 0:
        raise VirtualKeyboardError("min_height_delta_px must be positive")
    delta = before.viewport_height - after.viewport_height
    if delta < min_height_delta_px:
        raise VirtualKeyboardError(
            f"visualViewport only shrank by {delta:.0f}px, expected "
            f">= {min_height_delta_px}px — keyboard probably didn't show"
        )


def assert_keyboard_inset_set(snap: ViewportSnapshot) -> None:
    """The page should mirror keyboard inset into a CSS custom property
    so its layout can react."""
    raw = (snap.keyboard_inset or "").strip()
    if not raw or raw in ("0", "0px"):
        raise VirtualKeyboardError(
            "--keyboard-inset-height is unset or zero — layout cannot adapt"
        )


@dataclass
class FocusedElementBox:
    selector: str = ""
    top: float = 0
    bottom: float = 0


def assert_focused_visible(
    *, after: ViewportSnapshot, focused: FocusedElementBox,
) -> None:
    """The element currently focused (e.g. ``<input>``) must sit above
    the on-screen keyboard."""
    if focused.bottom > after.viewport_height + after.offset_top:
        raise VirtualKeyboardError(
            f"focused element {focused.selector!r} bottom={focused.bottom}px "
            f"is hidden behind keyboard "
            f"(visible viewport ends at {after.viewport_height + after.offset_top}px)"
        )
