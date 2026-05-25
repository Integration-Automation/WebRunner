"""
Multi-client email render compatibility audit (Outlook, Gmail, Apple Mail).

Outlook's MS-Word rendering engine still chokes on modern HTML/CSS —
flexbox, grid, ``calc()``, web fonts, SVG. Gmail strips ``<style>`` in
the ``<head>`` unless inline. Apple Mail honours dark-mode media queries.

This module audits an HTML email body for the most common
client-specific gotchas without launching a real Litmus/Email-on-Acid
account. It's a *pre-flight* check — not a substitute for visual QA.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List

from je_web_runner.utils.exception.exceptions import WebRunnerException


class InboxRenderOutlookError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class RenderFinding:
    rule: str
    severity: Severity
    message: str
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "severity": self.severity.value}


# Patterns flagged for Outlook (Word engine)
_OUTLOOK_BAD_CSS = (
    re.compile(r"\bdisplay\s*:\s*flex\b", re.IGNORECASE),
    re.compile(r"\bdisplay\s*:\s*grid\b", re.IGNORECASE),
    re.compile(r"\bcalc\s*\(", re.IGNORECASE),
    re.compile(r"\bposition\s*:\s*absolute\b", re.IGNORECASE),
    re.compile(r"\bbackground-image\s*:\s*linear-gradient", re.IGNORECASE),
    re.compile(r"\btransform\s*:\s*", re.IGNORECASE),
    re.compile(r"\b(?:transition|animation)\s*:", re.IGNORECASE),
)

# Patterns flagged for Gmail (no <style> in head unless inlined later)
_GMAIL_RULES = (
    re.compile(r"<style[^>]*>[^<]*@media", re.IGNORECASE | re.DOTALL),
)


_HTML_TYPE_ERROR = "html must be a string"


def audit_outlook(html: str) -> List[RenderFinding]:
    if not isinstance(html, str):
        raise InboxRenderOutlookError(_HTML_TYPE_ERROR)
    findings: List[RenderFinding] = []
    for pattern in _OUTLOOK_BAD_CSS:
        for match in pattern.finditer(html):
            findings.append(RenderFinding(
                rule="outlook-incompatible-css",
                severity=Severity.WARN,
                message=f"Outlook (Word renderer) doesn't support {match.group(0)!r}",
                snippet=html[max(0, match.start() - 20):match.end() + 20],
            ))
    if "<svg" in html.lower():
        findings.append(RenderFinding(
            rule="outlook-no-svg", severity=Severity.ERROR,
            message="Outlook renders <svg> as a broken-image placeholder",
        ))
    if not re.search(r"<table\b", html, re.IGNORECASE):
        findings.append(RenderFinding(
            rule="outlook-needs-table-layout", severity=Severity.WARN,
            message="No <table>-based layout — Outlook will not render columns",
        ))
    return findings


def audit_gmail(html: str) -> List[RenderFinding]:
    if not isinstance(html, str):
        raise InboxRenderOutlookError(_HTML_TYPE_ERROR)
    findings: List[RenderFinding] = []
    for pattern in _GMAIL_RULES:
        if pattern.search(html):
            findings.append(RenderFinding(
                rule="gmail-media-queries-need-inline",
                severity=Severity.INFO,
                message="Gmail strips <style>@media when forwarded — inline critical styles",
            ))
    # Gmail also clips messages > 102KB
    size = len(html.encode("utf-8"))
    if size > 102 * 1024:
        findings.append(RenderFinding(
            rule="gmail-message-clipping", severity=Severity.WARN,
            message=f"HTML body is {size}B (>102KB) — Gmail will clip with "
                    "[Message clipped] indicator",
        ))
    return findings


def audit_apple_mail(html: str) -> List[RenderFinding]:
    if not isinstance(html, str):
        raise InboxRenderOutlookError(_HTML_TYPE_ERROR)
    findings: List[RenderFinding] = []
    if "@media (prefers-color-scheme: dark)" not in html.lower():
        findings.append(RenderFinding(
            rule="apple-mail-dark-mode", severity=Severity.INFO,
            message="No prefers-color-scheme:dark @media block — "
                    "dark-mode users see auto-inverted (often broken) colours",
        ))
    return findings


def audit_all(html: str) -> List[RenderFinding]:
    return (audit_outlook(html) + audit_gmail(html) + audit_apple_mail(html))


def assert_no_errors(findings: Iterable[RenderFinding]) -> None:
    errors = [f for f in findings if f.severity == Severity.ERROR]
    if errors:
        raise InboxRenderOutlookError(
            f"render audit ERROR(s): {[f.rule for f in errors]}"
        )
