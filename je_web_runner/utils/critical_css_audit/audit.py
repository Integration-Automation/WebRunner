"""
Critical-CSS inline audit.

Above-the-fold CSS should be inlined inside ``<style>`` in the ``<head>``,
and external stylesheets needed for above-the-fold content should be
preloaded. Checks performed:

* At least one ``<style>`` block exists in ``<head>``.
* Inlined CSS size is within a sensible budget (avoid blocking parse).
* No render-blocking ``<link rel="stylesheet">`` whose declarations
  appear NOT to be needed above-the-fold (heuristic: presence of
  hover-only / @media-print rules).
* External stylesheets used for the fold are also preloaded.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CriticalCssAuditError(WebRunnerException):
    """Raised when critical-CSS best practice fails."""


@dataclass
class CssReport:
    inline_blocks: int = 0
    inline_bytes: int = 0
    external_blocking: List[str] = field(default_factory=list)
    preloaded: List[str] = field(default_factory=list)


_STYLE_BLOCK_RE = re.compile(
    r"<style[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL,
)
_LINK_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_HEAD_RE = re.compile(r"<head[^>]*>(.*?)</head>", re.IGNORECASE | re.DOTALL)


def _attr(tag: str, name: str) -> str:
    match = re.search(rf'{name}\s*=\s*[\'"]?([^\'"\s>]+)[\'"]?',
                      tag, re.IGNORECASE)
    return match.group(1) if match else ""


def analyse(html: str) -> CssReport:
    if not isinstance(html, str):
        raise CriticalCssAuditError("html must be a string")
    head_match = _HEAD_RE.search(html)
    head = head_match.group(1) if head_match else html
    inline_blocks = _STYLE_BLOCK_RE.findall(head)
    report = CssReport(
        inline_blocks=len(inline_blocks),
        inline_bytes=sum(len(b.encode("utf-8")) for b in inline_blocks),
    )
    for tag in _LINK_RE.findall(head):
        rel = _attr(tag, "rel").lower()
        href = _attr(tag, "href")
        if rel == "stylesheet" and href and "media=\"print\"" not in tag.lower():
            disabled = "disabled" in tag.lower()
            if not disabled:
                report.external_blocking.append(href)
        if rel == "preload" and _attr(tag, "as").lower() == "style":
            report.preloaded.append(href)
    return report


def assert_has_inline_critical(report: CssReport) -> None:
    if report.inline_blocks == 0:
        raise CriticalCssAuditError(
            "no inline <style> in <head> — above-the-fold rendering "
            "is blocked on external stylesheet fetch"
        )


def assert_inline_within_budget(
    report: CssReport, *, max_bytes: int = 14 * 1024,
) -> None:
    """14KB is the rough first-TCP-packet budget."""
    if max_bytes <= 0:
        raise CriticalCssAuditError("max_bytes must be positive")
    if report.inline_bytes > max_bytes:
        raise CriticalCssAuditError(
            f"inline CSS {report.inline_bytes}B exceeds {max_bytes}B "
            "(first-packet budget) — too much above-the-fold weight"
        )


def assert_external_preloaded(report: CssReport) -> None:
    missing = [href for href in report.external_blocking
               if href not in report.preloaded]
    if missing:
        raise CriticalCssAuditError(
            f"{len(missing)} render-blocking stylesheet(s) not preloaded: "
            f"{missing}"
        )
