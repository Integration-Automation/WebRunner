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
from dataclasses import dataclass, field
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ViewportAuditError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


@dataclass
class ViewportMeta:
    content: str = ""
    parsed: dict[str, str] = field(default_factory=dict)


def _parse_meta_content(content: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (content or "").split(","):
        if "=" in part:
            k, _, v = part.partition("=")
            out[k.strip().lower()] = v.strip().lower()
        elif part.strip():
            out[part.strip().lower()] = ""
    return out


_META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(
    r"""(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
    re.IGNORECASE,
)


def _tag_attrs(tag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in _ATTR_RE.finditer(tag):
        key = match.group(1).lower()
        out[key] = match.group(2) or match.group(3) or match.group(4) or ""
    return out


def parse_meta(html: str) -> ViewportMeta | None:
    """Extract the *last* ``<meta name="viewport">`` content from HTML."""
    if not isinstance(html, str):
        raise ViewportAuditError("html must be a string")
    last_content: str | None = None
    for tag in _META_TAG_RE.finditer(html):
        attrs = _tag_attrs(tag.group(0))
        if attrs.get("name", "").lower() == "viewport" and "content" in attrs:
            last_content = attrs["content"]
    if last_content is None:
        return None
    return ViewportMeta(content=last_content,
                        parsed=_parse_meta_content(last_content))


def assert_meta_present(meta: ViewportMeta | None) -> None:
    if meta is None:
        raise ViewportAuditError(
            "<meta name='viewport'> is missing — mobile layout will be broken"
        )


def assert_responsive_width(meta: ViewportMeta | None) -> None:
    assert_meta_present(meta)
    width = meta.parsed.get("width")
    if width != "device-width":
        raise ViewportAuditError(
            f"viewport width={width!r}, expected 'device-width'"
        )


def assert_user_scalable_allowed(meta: ViewportMeta | None) -> None:
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


def assert_notch_aware(meta: ViewportMeta | None) -> None:
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
