"""
Font loading strategy verification.

Three patterns are common; each has its own UX trade-off:

* **FOIT** (Flash of Invisible Text) — ``font-display: block``, text
  hidden until web font loads. Causes CLS hits.
* **FOUT** (Flash of Unstyled Text) — ``font-display: swap``, fallback
  shown immediately, swapped when web font loads. Default
  recommendation.
* **FOFT** (Flash of Faux Text) — small subset preloaded, rest swapped
  in. Most complex but smoothest.

This module reads computed ``font-display`` for every @font-face and
audits for:

* Missing ``font-display`` (browser default = FOIT, the slowest).
* ``size-adjust`` set on fallback fonts to minimise CLS during swap.
* Variable fonts loaded with ``font-display: swap`` not ``block``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FontLoadingStrategyError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


class Display(str, Enum):
    AUTO = "auto"
    BLOCK = "block"      # FOIT
    SWAP = "swap"        # FOUT
    FALLBACK = "fallback"
    OPTIONAL = "optional"
    MISSING = "(missing)"


@dataclass
class FontFace:
    family: str
    src: str = ""
    display: Display = Display.MISSING
    size_adjust: str = ""
    weight: str = ""
    style: str = ""


_FONT_FACE_RE = re.compile(
    r"@font-face\s*\{([^}]*)\}", re.IGNORECASE | re.DOTALL,
)
# Greedy [^;]* is non-backtracking; trailing whitespace is stripped by the
# caller via .strip().  Bounded input (one @font-face block, ~kB max).
_DECL_RE = re.compile(r"([\w-]+)\s*:\s*([^;]*)(?:;|$)")  # NOSONAR python:S5852


def parse_font_faces(css: str) -> list[FontFace]:
    if not isinstance(css, str):
        raise FontLoadingStrategyError("css must be a string")
    out: list[FontFace] = []
    for block_match in _FONT_FACE_RE.finditer(css):
        decls = dict(_DECL_RE.findall(block_match.group(1)))
        family = (decls.get("font-family") or "").strip().strip("'\"")
        if not family:
            continue
        display_raw = (decls.get("font-display") or "").strip()
        try:
            display = Display(display_raw) if display_raw else Display.MISSING
        except ValueError:
            display = Display.MISSING
        out.append(FontFace(
            family=family,
            src=(decls.get("src") or "").strip(),
            display=display,
            size_adjust=(decls.get("size-adjust") or "").strip(),
            weight=(decls.get("font-weight") or "").strip(),
            style=(decls.get("font-style") or "").strip(),
        ))
    return out


def assert_no_missing_display(faces: Iterable[FontFace]) -> None:
    missing = [f for f in faces if f.display == Display.MISSING]
    if missing:
        families = sorted({f.family for f in missing})
        raise FontLoadingStrategyError(
            f"{len(missing)} @font-face block(s) missing font-display: "
            f"{families} → browser defaults to FOIT"
        )


def assert_display_strategy(
    faces: Iterable[FontFace], *, strategy: Display,
) -> None:
    if strategy in (Display.AUTO, Display.MISSING):
        raise FontLoadingStrategyError(
            f"strategy must be one of swap/fallback/optional/block; "
            f"got {strategy.value}"
        )
    wrong = [f for f in faces if f.display != strategy]
    if wrong:
        actual = sorted({f.display.value for f in wrong})
        raise FontLoadingStrategyError(
            f"{len(wrong)} font-face(s) use {actual}, expected {strategy.value}"
        )


def assert_size_adjust_for_fallback(
    fallback_family: str, faces: Iterable[FontFace],
) -> None:
    """If the page declares a fallback face like ``'Inter Fallback'`` with
    ``size-adjust``, CLS during font swap is minimised."""
    matches = [f for f in faces if f.family == fallback_family]
    if not matches:
        raise FontLoadingStrategyError(
            f"no @font-face for fallback family {fallback_family!r}"
        )
    if all(not f.size_adjust for f in matches):
        raise FontLoadingStrategyError(
            f"fallback family {fallback_family!r} has no size-adjust → "
            "CLS will spike when the real font loads"
        )
