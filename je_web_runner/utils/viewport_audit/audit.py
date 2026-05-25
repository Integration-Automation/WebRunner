"""
Viewport meta + safe-area + notch handling audit.

Common mobile bugs this catches:

* Missing or broken ``<meta name="viewport">``.
* ``user-scalable=no`` (a11y violation, banned on Apple App Store reviews).
* Missing ``viewport-fit=cover`` on apps that draw under the iOS notch.
* Pages whose body uses ``padding: 0`` instead of
  ``padding: env(safe-area-inset-top)`` on notched devices.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ViewportAuditError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


@dataclass
class ViewportMeta:
    content: str = ""
    parsed: Dict[str, str] = field(default_factory=dict)


def _parse_meta_content(content: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in (content or "").split(","):
        if "=" in part:
            k, _, v = part.partition("=")
            out[k.strip().lower()] = v.strip().lower()
        elif part.strip():
            out[part.strip().lower()] = ""
    return out


def parse_meta(html: str) -> Optional[ViewportMeta]:
    """Extract the *last* ``<meta name="viewport">`` content from HTML."""
    if not isinstance(html, str):
        raise ViewportAuditError("html must be a string")
    matches = re.findall(
        r'<meta\s+[^>]*name=[\'"]viewport[\'"][^>]*content=[\'"]([^\'"]*)[\'"]',
        html, flags=re.IGNORECASE,
    )
    if not matches:
        return None
    last = matches[-1]
    return ViewportMeta(content=last, parsed=_parse_meta_content(last))


def assert_meta_present(meta: Optional[ViewportMeta]) -> None:
    if meta is None:
        raise ViewportAuditError(
            "<meta name='viewport'> is missing — mobile layout will be broken"
        )


def assert_responsive_width(meta: Optional[ViewportMeta]) -> None:
    assert_meta_present(meta)
    width = meta.parsed.get("width")
    if width != "device-width":
        raise ViewportAuditError(
            f"viewport width={width!r}, expected 'device-width'"
        )


def assert_user_scalable_allowed(meta: Optional[ViewportMeta]) -> None:
    """A11y / WCAG 1.4.4: pinch-zoom must not be disabled."""
    assert_meta_present(meta)
    scalable = meta.parsed.get("user-scalable")
    if scalable in ("no", "0"):
        raise ViewportAuditError(
            "viewport disables user-scalable — WCAG 1.4.4 violation"
        )
    max_scale = meta.parsed.get("maximum-scale")
    if max_scale and max_scale not in ("", "0"):
        try:
            if float(max_scale) < 2.0:
                raise ViewportAuditError(
                    f"maximum-scale={max_scale} < 2.0 — pinch-zoom is "
                    "effectively disabled (WCAG 1.4.4 violation)"
                )
        except ValueError as exc:
            raise ViewportAuditError(
                f"maximum-scale must be numeric, got {max_scale!r}"
            ) from exc


def assert_notch_aware(meta: Optional[ViewportMeta]) -> None:
    assert_meta_present(meta)
    fit = meta.parsed.get("viewport-fit")
    if fit != "cover":
        raise ViewportAuditError(
            f"viewport-fit={fit!r}, expected 'cover' "
            "for apps drawing under the iOS notch"
        )


# ---- safe-area CSS audit -------------------------------------------------

@dataclass
class SafeAreaSnapshot:
    """Captured at runtime from the page (via getComputedStyle on <body>)."""

    padding_top: str = "0px"
    padding_bottom: str = "0px"
    padding_left: str = "0px"
    padding_right: str = "0px"


HARVEST_SCRIPT = r"""
(function () {
  const cs = getComputedStyle(document.body);
  return {
    padding_top: cs.paddingTop,
    padding_bottom: cs.paddingBottom,
    padding_left: cs.paddingLeft,
    padding_right: cs.paddingRight,
  };
})();
"""


def parse_safe_area(payload: Any) -> SafeAreaSnapshot:
    if not isinstance(payload, dict):
        raise ViewportAuditError("payload must be a dict")
    return SafeAreaSnapshot(
        padding_top=str(payload.get("padding_top") or "0px"),
        padding_bottom=str(payload.get("padding_bottom") or "0px"),
        padding_left=str(payload.get("padding_left") or "0px"),
        padding_right=str(payload.get("padding_right") or "0px"),
    )


def _is_zero(value: str) -> bool:
    return value.strip().replace("px", "") in ("", "0")


def assert_safe_area_padding(snap: SafeAreaSnapshot) -> None:
    """At least one of the four body paddings must be non-zero on a
    notched device — pages that don't bake env(safe-area-inset-*) into
    their CSS will report all zeros."""
    if all(_is_zero(v) for v in (snap.padding_top, snap.padding_bottom,
                                 snap.padding_left, snap.padding_right)):
        raise ViewportAuditError(
            "body padding is zero in every direction — page likely doesn't "
            "use env(safe-area-inset-*) and will be clipped by the notch"
        )
