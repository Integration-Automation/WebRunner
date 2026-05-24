"""
SSR hydration mismatch 偵測。
React 18, Next.js, Nuxt 3, Remix, SvelteKit 都會印 hydration error 到
console — 但 prod 預設靜默。常見錯誤:

* 伺服器渲染的 markup 跟 client 第一次 hydration 結果不同
* ``new Date()`` / ``Math.random()`` 在 server vs client 結果不同
* Provider 用 `useState(window.x)` 之類 SSR-incompatible 寫法

This module:

* Compares the *raw server HTML* (fetched as bytes) against the
  *post-hydration DOM* (innerHTML snapshot). It normalises whitespace,
  React data-attribs (``data-reactroot``), and Vue / SvelteKit hashes.
* Parses console messages for known hydration error markers and surfaces
  them as findings.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class HydrationCheckError(WebRunnerException):
    """Raised on malformed input or failed assertion."""


# Markers each framework prints on hydration mismatch.
_HYDRATION_MARKERS = (
    "hydration failed",                          # React 18
    "did not match",                             # React 17/18
    "expected server html to contain",           # React
    "hydration mismatch",                        # Vue 3, Svelte
    "skipping hydration",                        # Astro
    "error while hydrating",                     # Nuxt
    "text content does not match server-rendered html",  # React 18
)


@dataclass(frozen=True)
class HydrationFinding:
    """One detected hydration problem."""

    kind: str  # 'console' | 'dom_diff'
    detail: str
    source: str = ""


# ---------- console scan ----------------------------------------------

def scan_console(messages: Iterable[str]) -> List[HydrationFinding]:
    """Pull hydration-related lines out of console messages."""
    findings: List[HydrationFinding] = []
    for line in messages:
        if not isinstance(line, str):
            continue
        lower = line.lower()
        for marker in _HYDRATION_MARKERS:
            if marker in lower:
                findings.append(HydrationFinding(
                    kind="console", detail=line.strip()[:200], source=marker,
                ))
                break
    return findings


# ---------- DOM diff --------------------------------------------------

_WS = re.compile(r"\s+")
# NOSONAR python:S5852 — input is a finite SSR HTML snapshot, not attacker text
_WS_AROUND_TAGS = re.compile(r"\s*(<[^>]+>)\s*")  # noqa: S5852
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_FRAMEWORK_ATTRS = re.compile(
    r"\s+(?:data-reactroot|data-reactid|data-react-helmet|data-n-head|"
    r"data-v-[a-f0-9]+|data-svelte-h)\b(?:=\"[^\"]*\")?",
    re.IGNORECASE,
)
_SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)


def _normalise_html(html: str) -> str:
    text = _SCRIPT_BLOCK.sub("", html)
    text = _COMMENT.sub("", text)  # also removes React's <!--$--> / <!--/$--> markers
    text = _FRAMEWORK_ATTRS.sub("", text)
    text = _WS_AROUND_TAGS.sub(r"\1", text)
    text = _WS.sub(" ", text).strip().lower()
    return text


def diff_dom(server_html: str, client_html: str) -> List[HydrationFinding]:
    """
    Compare server-rendered HTML to post-hydration HTML.
    Returns findings only if the *normalised* representations differ.
    """
    if not isinstance(server_html, str) or not isinstance(client_html, str):
        raise HydrationCheckError("server_html and client_html must be strings")
    server_n = _normalise_html(server_html)
    client_n = _normalise_html(client_html)
    if server_n == client_n:
        return []
    # Find the first diverging chunk for a useful detail string.
    common = 0
    while (
        common < len(server_n) and common < len(client_n)
        and server_n[common] == client_n[common]
    ):
        common += 1
    s_excerpt = server_n[common:common + 80]
    c_excerpt = client_n[common:common + 80]
    return [HydrationFinding(
        kind="dom_diff",
        detail=f"diverged at char {common}: server={s_excerpt!r} client={c_excerpt!r}",
    )]


# ---------- combined --------------------------------------------------

@dataclass
class HydrationReport:
    """Combined console + DOM-diff finding set."""

    findings: List[HydrationFinding] = field(default_factory=list)

    def passed(self) -> bool:
        return not self.findings

    def by_kind(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for f in self.findings:
            out[f.kind] = out.get(f.kind, 0) + 1
        return out


def audit(
    *,
    server_html: Optional[str] = None,
    client_html: Optional[str] = None,
    console_messages: Optional[Iterable[str]] = None,
) -> HydrationReport:
    """Run all available checks. Either pair of inputs may be ``None``."""
    findings: List[HydrationFinding] = []
    if server_html is not None and client_html is not None:
        findings.extend(diff_dom(server_html, client_html))
    if console_messages is not None:
        findings.extend(scan_console(console_messages))
    return HydrationReport(findings=findings)


def assert_no_mismatch(report: HydrationReport) -> None:
    """Raise unless ``report`` is clean."""
    if not isinstance(report, HydrationReport):
        raise HydrationCheckError("assert_no_mismatch expects HydrationReport")
    if report.passed():
        return
    sample = ", ".join(f"{f.kind}:{f.detail[:60]}" for f in report.findings[:3])
    more = "" if len(report.findings) <= 3 else f" (+{len(report.findings) - 3})"
    raise HydrationCheckError(f"hydration mismatch detected: {sample}{more}")
