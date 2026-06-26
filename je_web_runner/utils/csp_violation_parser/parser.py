"""
Content Security Policy violation report parser & classifier.

Reads ``report-uri`` / ``report-to`` JSON payloads (both legacy and v3
formats) and:

* Normalises into a single ``Violation`` record.
* Buckets by violated directive (``script-src``, ``style-src``, ...).
* Surfaces the top blocked URI and offending hosts.
* Flags signs of trial-and-error reconnaissance (many distinct
  blocked-host attempts to the same directive in a short window).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CspViolationParserError(WebRunnerException):
    """Raised on malformed input."""


@dataclass
class Violation:
    document_uri: str = ""
    referrer: str = ""
    violated_directive: str = ""
    blocked_uri: str = ""
    source_file: str = ""
    line_number: int = 0
    disposition: str = "enforce"   # "enforce" | "report"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_one(report: Any) -> Violation:
    if not isinstance(report, dict):
        raise CspViolationParserError("report must be a dict")
    # Legacy: {"csp-report": {...}}
    body = report.get("csp-report") if "csp-report" in report else report
    if not isinstance(body, dict):
        raise CspViolationParserError("csp-report body must be a dict")
    return Violation(
        document_uri=str(body.get("document-uri") or body.get("documentURL") or ""),
        referrer=str(body.get("referrer") or ""),
        violated_directive=str(
            body.get("violated-directive") or body.get("effectiveDirective") or "",
        ),
        blocked_uri=str(body.get("blocked-uri") or body.get("blockedURL") or ""),
        source_file=str(body.get("source-file") or body.get("sourceFile") or ""),
        line_number=int(body.get("line-number") or body.get("lineNumber") or 0),
        disposition=str(body.get("disposition") or "enforce"),
    )


def parse_many(reports: Iterable[Any]) -> list[Violation]:
    return [parse_one(r) for r in reports]


def group_by_directive(
    violations: Iterable[Violation],
) -> dict[str, list[Violation]]:
    buckets: dict[str, list[Violation]] = defaultdict(list)
    for v in violations:
        buckets[v.violated_directive or "(unknown)"].append(v)
    return dict(buckets)


def top_blocked_hosts(
    violations: Iterable[Violation], *, top_n: int = 5,
) -> list[dict[str, Any]]:
    if top_n < 1:
        raise CspViolationParserError("top_n must be >= 1")
    counts: Counter = Counter()
    for v in violations:
        host = urlparse(v.blocked_uri).hostname or v.blocked_uri
        if host:
            counts[host] += 1
    return [{"host": h, "count": c} for h, c in counts.most_common(top_n)]


def assert_no_enforced_violations(violations: Iterable[Violation]) -> None:
    enforced = [v for v in violations if v.disposition == "enforce"]
    if enforced:
        directives = sorted({v.violated_directive for v in enforced})
        raise CspViolationParserError(
            f"{len(enforced)} enforced CSP violation(s) "
            f"affecting directives: {directives}"
        )


def looks_like_recon(
    violations: Iterable[Violation], *, distinct_hosts_threshold: int = 5,
) -> list[str]:
    """Buckets per directive whose distinct blocked-host count exceeds
    ``distinct_hosts_threshold`` — a probable XSS / SSRF probe."""
    if distinct_hosts_threshold < 2:
        raise CspViolationParserError(
            "distinct_hosts_threshold must be >= 2"
        )
    hosts_by_directive: dict[str, set] = defaultdict(set)
    for v in violations:
        host = urlparse(v.blocked_uri).hostname or v.blocked_uri
        if host:
            hosts_by_directive[v.violated_directive].add(host)
    return [d for d, hosts in hosts_by_directive.items()
            if len(hosts) >= distinct_hosts_threshold]
