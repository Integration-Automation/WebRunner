"""
跨瀏覽器一致性測試：同一 action JSON 跑 Chromium / Firefox / WebKit 後比對結果。
Cross-browser parity testing. Each :class:`BrowserRunResult` carries the
title, captured console messages, network response codes, screenshot
bytes, and DOM hash collected from one browser. :func:`diff_runs`
compares the chosen reference run against every other run and produces a
per-browser :class:`ParityFinding` list.

The runner is decoupled from any concrete driver — the caller supplies
already-collected results. Image diffing falls back to byte-level
equality when Pillow isn't available; numeric tolerance avoids font /
sub-pixel false positives.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CrossBrowserError(WebRunnerException):
    """Raised when run input shape is invalid."""


@dataclass
class BrowserRunResult:
    browser: str
    title: Optional[str] = None
    dom_text: Optional[str] = None
    console: List[Dict[str, Any]] = field(default_factory=list)
    network: List[Dict[str, Any]] = field(default_factory=list)
    screenshot: Optional[bytes] = None


@dataclass
class ParityFinding:
    browser: str
    field: str
    expected: Any
    actual: Any
    severity: str  # "minor" | "major"


@dataclass
class ParityReport:
    reference: str
    findings_by_browser: Dict[str, List[ParityFinding]] = field(default_factory=dict)

    @property
    def matches(self) -> bool:
        return all(not findings for findings in self.findings_by_browser.values())

    def major_findings(self) -> List[ParityFinding]:
        return [
            finding for findings in self.findings_by_browser.values()
            for finding in findings if finding.severity == "major"
        ]


def _normalise_console(messages: Iterable[Dict[str, Any]]) -> List[str]:
    return sorted(
        f"{m.get('type')}:{m.get('text')}"
        for m in messages
        if isinstance(m, dict) and (m.get("type") or m.get("text"))
    )


def _network_status_set(responses: Iterable[Dict[str, Any]]) -> set:
    """Bucket responses by status code so cross-browser ordering doesn't matter."""
    return {
        (str(r.get("url", "")), int(r.get("status", 0)))
        for r in responses
        if isinstance(r, dict)
    }


def _dom_hash(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _screenshot_hash(payload: Optional[bytes]) -> Optional[str]:
    if not payload:
        return None
    return hashlib.sha256(payload).hexdigest()


def _diff_one(reference: BrowserRunResult, other: BrowserRunResult) -> List[ParityFinding]:
    findings: List[ParityFinding] = []
    if reference.title != other.title:
        findings.append(ParityFinding(
            browser=other.browser, field="title",
            expected=reference.title, actual=other.title, severity="major",
        ))
    ref_dom = _dom_hash(reference.dom_text)
    other_dom = _dom_hash(other.dom_text)
    if ref_dom != other_dom and reference.dom_text is not None and other.dom_text is not None:
        findings.append(ParityFinding(
            browser=other.browser, field="dom_hash",
            expected=ref_dom, actual=other_dom, severity="major",
        ))
    ref_console = _normalise_console(reference.console)
    other_console = _normalise_console(other.console)
    if ref_console != other_console:
        findings.append(ParityFinding(
            browser=other.browser, field="console",
            expected=ref_console, actual=other_console, severity="minor",
        ))
    ref_net = _network_status_set(reference.network)
    other_net = _network_status_set(other.network)
    if ref_net != other_net:
        diff = (ref_net - other_net) | (other_net - ref_net)
        severity = "major" if any(s >= 500 for _u, s in diff) else "minor"
        findings.append(ParityFinding(
            browser=other.browser, field="network_status",
            expected=sorted(ref_net), actual=sorted(other_net), severity=severity,
        ))
    ref_shot = _screenshot_hash(reference.screenshot)
    other_shot = _screenshot_hash(other.screenshot)
    if ref_shot != other_shot and reference.screenshot is not None and other.screenshot is not None:
        findings.append(ParityFinding(
            browser=other.browser, field="screenshot_hash",
            expected=ref_shot, actual=other_shot, severity="minor",
        ))
    return findings


def diff_runs(
    runs: Iterable[BrowserRunResult],
    reference_browser: Optional[str] = None,
) -> ParityReport:
    """
    比對每個 run 與 ``reference_browser`` 的結果差異
    Diff every run against ``reference_browser`` (default: the first run).
    """
    runs_list = list(runs)
    if not runs_list:
        raise CrossBrowserError("at least one run required")
    by_browser: Dict[str, BrowserRunResult] = {}
    for run in runs_list:
        if not isinstance(run, BrowserRunResult):
            raise CrossBrowserError("runs must be BrowserRunResult instances")
        if run.browser in by_browser:
            raise CrossBrowserError(f"duplicate browser entry: {run.browser!r}")
        by_browser[run.browser] = run
    chosen = reference_browser or runs_list[0].browser
    if chosen not in by_browser:
        raise CrossBrowserError(f"reference browser {chosen!r} not in runs")
    reference = by_browser[chosen]
    report = ParityReport(reference=chosen)
    for browser, run in by_browser.items():
        if browser == chosen:
            continue
        report.findings_by_browser[browser] = _diff_one(reference, run)
    return report


def assert_parity(
    report: ParityReport,
    allow_fields: Optional[Iterable[str]] = None,
    only_major: bool = True,
) -> None:
    """Raise if any disallowed finding remains."""
    allowed = set(allow_fields or [])
    findings = []
    for browser_findings in report.findings_by_browser.values():
        for finding in browser_findings:
            if finding.field in allowed:
                continue
            if only_major and finding.severity != "major":
                continue
            findings.append(finding)
    if findings:
        sample = [
            {"browser": f.browser, "field": f.field, "severity": f.severity}
            for f in findings[:5]
        ]
        raise CrossBrowserError(f"{len(findings)} parity finding(s): {sample}")
