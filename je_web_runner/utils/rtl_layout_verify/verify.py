"""
RTL (right-to-left) layout sanity verification for Arabic / Hebrew /
Persian locales.

The browser-side ``HARVEST_SCRIPT`` collects bounding boxes + the resolved
``direction`` / ``writing-mode`` for a set of selectors. The Python side
then checks:

* The document has ``dir="rtl"``.
* Visual order of siblings is reversed vs. LTR (rightmost child appears
  first in DOM-paint order).
* Logical-property usage (no leftover ``margin-left`` where ``margin-inline-start``
  was expected).
* No bidi text-leakage (English fragment inside Arabic paragraph without
  ``<bdi>`` or ``unicode-bidi: isolate``).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class RtlLayoutVerifyError(WebRunnerException):
    """Raised when RTL invariants are violated."""


HARVEST_SCRIPT = r"""
(function () {
  function box(el) {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(),
      id: el.id || '',
      text: (el.textContent || '').slice(0, 80),
      left: r.left, right: r.right, top: r.top, bottom: r.bottom,
      direction: cs.direction,
      writingMode: cs.writingMode,
      marginLeft: cs.marginLeft,
      marginRight: cs.marginRight,
      paddingLeft: cs.paddingLeft,
      paddingRight: cs.paddingRight,
      unicodeBidi: cs.unicodeBidi,
    };
  }
  const selectors = arguments[0];
  const out = { documentDir: document.documentElement.dir, items: [] };
  for (const sel of selectors) {
    const els = Array.from(document.querySelectorAll(sel));
    out.items.push({ selector: sel, boxes: els.map(box) });
  }
  return out;
})();
"""


@dataclass
class ElementBox:
    tag: str
    text: str = ""
    left: float = 0
    right: float = 0
    direction: str = "ltr"
    writing_mode: str = "horizontal-tb"
    margin_left: str = "0px"
    margin_right: str = "0px"
    padding_left: str = "0px"
    padding_right: str = "0px"
    unicode_bidi: str = "normal"
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Snapshot:
    document_dir: str
    selectors: Dict[str, List[ElementBox]] = field(default_factory=dict)


def parse_snapshot(payload: Any) -> Snapshot:
    if not isinstance(payload, dict):
        raise RtlLayoutVerifyError("payload must be a dict")
    snap = Snapshot(document_dir=str(payload.get("documentDir") or ""))
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        selector = item.get("selector")
        boxes_raw = item.get("boxes") or []
        if not isinstance(selector, str):
            continue
        boxes: List[ElementBox] = []
        for raw in boxes_raw:
            if not isinstance(raw, dict):
                continue
            boxes.append(ElementBox(
                tag=str(raw.get("tag") or ""),
                text=str(raw.get("text") or ""),
                left=float(raw.get("left") or 0),
                right=float(raw.get("right") or 0),
                direction=str(raw.get("direction") or "ltr"),
                writing_mode=str(raw.get("writingMode") or "horizontal-tb"),
                margin_left=str(raw.get("marginLeft") or "0px"),
                margin_right=str(raw.get("marginRight") or "0px"),
                padding_left=str(raw.get("paddingLeft") or "0px"),
                padding_right=str(raw.get("paddingRight") or "0px"),
                unicode_bidi=str(raw.get("unicodeBidi") or "normal"),
                raw=raw,
            ))
        snap.selectors[selector] = boxes
    return snap


def assert_document_rtl(snap: Snapshot) -> None:
    if snap.document_dir.lower() != "rtl":
        raise RtlLayoutVerifyError(
            f"<html dir> is {snap.document_dir!r}, expected 'rtl'"
        )


def _is_zero(margin: str) -> bool:
    return margin.replace("px", "").strip() in ("0", "")


def assert_logical_properties(snap: Snapshot, selector: str) -> None:
    """Flag boxes with non-zero margin-left where margin-right is zero in RTL."""
    boxes = snap.selectors.get(selector)
    if not boxes:
        raise RtlLayoutVerifyError(f"selector {selector!r} not in snapshot")
    offenders = [
        b for b in boxes
        if b.direction == "rtl"
        and not _is_zero(b.margin_left) and _is_zero(b.margin_right)
    ]
    if offenders:
        raise RtlLayoutVerifyError(
            f"{len(offenders)} RTL element(s) use margin-left "
            f"(physical) instead of margin-inline-start (logical)"
        )


def assert_visual_order_reversed(snap: Snapshot, selector: str) -> None:
    """In RTL, the first sibling should be the right-most on screen."""
    boxes = snap.selectors.get(selector)
    if not boxes or len(boxes) < 2:
        raise RtlLayoutVerifyError(
            f"selector {selector!r} needs >=2 siblings to check order"
        )
    # ignore elements stacked vertically (different rows)
    horizontal = [b for b in boxes
                  if abs(b.left) + abs(b.right) > 0]
    if len(horizontal) < 2:
        raise RtlLayoutVerifyError("not enough horizontal siblings to check")
    first, last = horizontal[0], horizontal[-1]
    if first.left <= last.left:
        raise RtlLayoutVerifyError(
            f"siblings not visually reversed under RTL "
            f"(first.left={first.left}, last.left={last.left})"
        )


def assert_bidi_isolation(snap: Snapshot, selector: str) -> None:
    """Latin text inside RTL container should use bdi / unicode-bidi: isolate."""
    boxes = snap.selectors.get(selector)
    if not boxes:
        raise RtlLayoutVerifyError(f"selector {selector!r} not in snapshot")
    leaks = []
    for b in boxes:
        if b.direction != "rtl":
            continue
        if any(c.isascii() and c.isalpha() for c in b.text):
            if "isolate" not in b.unicode_bidi and b.tag != "bdi":
                leaks.append(b.text[:40])
    if leaks:
        raise RtlLayoutVerifyError(
            f"bidi leak: {len(leaks)} Latin fragment(s) in RTL without "
            f"isolation, e.g. {leaks[:3]}"
        )
