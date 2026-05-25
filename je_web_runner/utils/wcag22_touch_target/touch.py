"""
WCAG 2.2 SC 2.5.8 (Target Size — Minimum, AA) auditor.

Interactive elements must have a target size of at least 24×24 CSS pixels
*unless* one of the exceptions applies:

* The element is inline within a text block.
* The element is in a "user-agent" group (e.g. native form controls).
* The element has been determined essential to be smaller.
* The element is replaced by an equivalent larger alternative.

This module:

* Provides a harvest JS script that reports for each candidate element its
  bounding box, role, parent context (is it inside a paragraph?), and any
  adjacent gap to other interactive elements (the "spacing" exception
  allows a 24-px circle even if the element itself is smaller).
* Audits the resulting payload and emits findings with exception
  classification.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List

from je_web_runner.utils.exception.exceptions import WebRunnerException


class Wcag22TouchTargetError(WebRunnerException):
    """Raised on malformed input or violation aggregation."""


MIN_SIZE_CSS_PX = 24


HARVEST_SCRIPT = r"""
(function () {
  const interactive = 'a[href],button,input:not([type="hidden"]),' +
                      'select,textarea,[role="button"],[role="link"],' +
                      '[tabindex]:not([tabindex="-1"])';
  const out = [];
  const all = Array.from(document.querySelectorAll(interactive));
  function rect(el) {
    const r = el.getBoundingClientRect();
    return {
      x: r.left, y: r.top, width: r.width, height: r.height,
    };
  }
  for (const el of all) {
    const r = rect(el);
    if (r.width === 0 || r.height === 0) continue;
    const parent = el.closest('p,li,td,h1,h2,h3,h4,h5,h6');
    out.push({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      type: el.getAttribute('type') || '',
      width: r.width, height: r.height, x: r.x, y: r.y,
      label: (el.textContent || el.getAttribute('aria-label') || '')
        .trim().slice(0, 40),
      isInlineInText: !!parent && parent !== el,
      isUserAgentControl: ['input','select','textarea'].includes(
        el.tagName.toLowerCase()
      ),
    });
  }
  return out;
})();
"""


class TargetException(str, Enum):
    INLINE_TEXT = "inline-in-text"
    USER_AGENT = "user-agent-control"
    SPACING = "spacing-circle"


@dataclass
class Target:
    tag: str = ""
    role: str = ""
    width: float = 0
    height: float = 0
    x: float = 0
    y: float = 0
    label: str = ""
    is_inline_in_text: bool = False
    is_user_agent_control: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def smallest_side(self) -> float:
        return min(self.width, self.height)


@dataclass
class Violation:
    label: str
    tag: str
    width: float
    height: float
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_targets(payload: Any) -> List[Target]:
    if not isinstance(payload, list):
        raise Wcag22TouchTargetError("payload must be a list")
    out: List[Target] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        out.append(Target(
            tag=str(raw.get("tag") or ""),
            role=str(raw.get("role") or ""),
            width=float(raw.get("width") or 0),
            height=float(raw.get("height") or 0),
            x=float(raw.get("x") or 0),
            y=float(raw.get("y") or 0),
            label=str(raw.get("label") or ""),
            is_inline_in_text=bool(raw.get("isInlineInText")),
            is_user_agent_control=bool(raw.get("isUserAgentControl")),
            raw=raw,
        ))
    return out


def _distance(a: Target, b: Target) -> float:
    ax = a.x + a.width / 2
    ay = a.y + a.height / 2
    bx = b.x + b.width / 2
    by = b.y + b.height / 2
    return math.hypot(ax - bx, ay - by)


def _has_spacing_circle(
    target: Target, others: Iterable[Target], min_diameter: float = MIN_SIZE_CSS_PX,
) -> bool:
    """Spacing exception: no other interactive element within a 24-px circle."""
    for other in others:
        if other is target:
            continue
        if _distance(target, other) < min_diameter:
            return False
    return True


def audit(targets: List[Target]) -> List[Violation]:
    """Return a list of Violation entries for elements failing 2.5.8."""
    if not isinstance(targets, list):
        raise Wcag22TouchTargetError("targets must be a list")
    violations: List[Violation] = []
    for t in targets:
        if t.smallest_side >= MIN_SIZE_CSS_PX:
            continue
        if t.is_inline_in_text:
            continue
        if t.is_user_agent_control:
            continue
        if _has_spacing_circle(t, targets):
            continue
        violations.append(Violation(
            label=t.label or "(no label)",
            tag=t.tag,
            width=t.width,
            height=t.height,
            note=(
                f"smallest side {t.smallest_side:.1f}px < {MIN_SIZE_CSS_PX}px "
                f"and no spacing-circle exception"
            ),
        ))
    return violations


def assert_no_violations(violations: Iterable[Violation]) -> None:
    items = list(violations)
    if items:
        raise Wcag22TouchTargetError(
            f"WCAG 2.5.8 violations: {[v.label for v in items]}"
        )
