"""
COOP / COEP / CORP cross-origin isolation header 稽核。
SharedArrayBuffer, high-resolution timers, WebGPU, and an increasing
number of "powerful" APIs require ``crossOriginIsolated`` to be true.
That needs:

* ``Cross-Origin-Opener-Policy: same-origin``  (COOP)
* ``Cross-Origin-Embedder-Policy: require-corp`` or ``credentialless`` (COEP)
* Every cross-origin sub-resource served with ``Cross-Origin-Resource-Policy``
  or CORS that satisfies COEP.

This module parses headers (page + per-resource HAR) and reports what
prevents isolation, with actionable detail rather than just yes/no.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CoopCoepAuditError(WebRunnerException):
    """Raised on bad header / HAR input or failed assertion."""


# ---------- enums ------------------------------------------------------

class CoopValue(str, Enum):
    UNSAFE_NONE = "unsafe-none"
    SAME_ORIGIN_ALLOW_POPUPS = "same-origin-allow-popups"
    SAME_ORIGIN = "same-origin"


class CoepValue(str, Enum):
    UNSAFE_NONE = "unsafe-none"
    CREDENTIALLESS = "credentialless"
    REQUIRE_CORP = "require-corp"


class CorpValue(str, Enum):
    SAME_SITE = "same-site"
    SAME_ORIGIN = "same-origin"
    CROSS_ORIGIN = "cross-origin"


# ---------- header parsing ---------------------------------------------

def _enum_or(value: Optional[str], cls, default):
    if value is None:
        return default
    try:
        return cls(value.strip().lower())
    except ValueError:
        return default


@dataclass
class PagePolicy:
    """Cross-origin-isolation policy for the top-level document."""

    coop: CoopValue = CoopValue.UNSAFE_NONE
    coep: CoepValue = CoepValue.UNSAFE_NONE

    def isolated(self) -> bool:
        return (
            self.coop == CoopValue.SAME_ORIGIN
            and self.coep in (CoepValue.REQUIRE_CORP, CoepValue.CREDENTIALLESS)
        )


def parse_page_headers(
    headers: Iterable[Tuple[str, str]],
) -> PagePolicy:
    """Parse a header iterable into a :class:`PagePolicy`."""
    coop_raw: Optional[str] = None
    coep_raw: Optional[str] = None
    for name, value in headers:
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        n = name.strip().lower()
        if n == "cross-origin-opener-policy":
            coop_raw = value
        elif n == "cross-origin-embedder-policy":
            coep_raw = value
    return PagePolicy(
        coop=_enum_or(coop_raw, CoopValue, CoopValue.UNSAFE_NONE),
        coep=_enum_or(coep_raw, CoepValue, CoepValue.UNSAFE_NONE),
    )


# ---------- per-resource audit ----------------------------------------

@dataclass
class ResourceFinding:
    """One sub-resource that violates COEP."""

    url: str
    reason: str
    corp: Optional[str] = None
    cors_present: bool = False


def _same_origin(a: str, b: str) -> bool:
    try:
        pa = urlparse(a)
        pb = urlparse(b)
    except ValueError:
        return False
    return (pa.scheme, pa.hostname, pa.port) == (pb.scheme, pb.hostname, pb.port)


def _header_lookup(entry: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    headers = ((entry.get("response") or {}).get("headers")) or []
    if not isinstance(headers, list):
        return out
    for h in headers:
        if not isinstance(h, dict):
            continue
        name = h.get("name")
        value = h.get("value")
        if isinstance(name, str) and isinstance(value, str):
            out[name.strip().lower()] = value
    return out


def scan_har_resources(
    har: Union[str, Dict[str, Any]],
    *,
    page_url: str,
    coep: CoepValue,
) -> List[ResourceFinding]:
    """
    Walk HAR entries; any cross-origin entry must satisfy the page's COEP.
    Returns one :class:`ResourceFinding` per violation; empty list means OK.
    """
    if coep == CoepValue.UNSAFE_NONE:
        return []
    if not isinstance(page_url, str) or not page_url:
        raise CoopCoepAuditError("page_url must be non-empty string")
    har_obj = _coerce_har(har)
    entries = ((har_obj.get("log") or {}).get("entries")) or []
    if not isinstance(entries, list):
        raise CoopCoepAuditError("har log.entries must be a list")
    findings: List[ResourceFinding] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        request_url = ((entry.get("request") or {}).get("url")) or ""
        if not request_url or _same_origin(request_url, page_url):
            continue
        headers = _header_lookup(entry)
        corp = headers.get("cross-origin-resource-policy")
        cors_origin = headers.get("access-control-allow-origin")
        cors_credentials = headers.get("access-control-allow-credentials")
        if coep == CoepValue.REQUIRE_CORP:
            if corp == CorpValue.CROSS_ORIGIN.value:
                continue
            if cors_origin and cors_origin != "null":
                continue
            findings.append(ResourceFinding(
                url=request_url,
                reason="require-corp: needs CORP cross-origin OR CORS allow",
                corp=corp, cors_present=bool(cors_origin),
            ))
        elif coep == CoepValue.CREDENTIALLESS:
            # credentialless allows credentialled requests to fail open but
            # still requires CORP or CORS for credentialled fetches.
            if corp or cors_origin:
                continue
            findings.append(ResourceFinding(
                url=request_url,
                reason="credentialless: needs CORP or CORS",
                corp=corp, cors_present=bool(cors_origin),
            ))
    return findings


def _coerce_har(har: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(har, str):
        try:
            parsed = json.loads(har)
        except ValueError as error:
            raise CoopCoepAuditError(f"har not JSON: {error}") from error
        if not isinstance(parsed, dict):
            raise CoopCoepAuditError("har JSON must be an object")
        return parsed
    if isinstance(har, dict):
        return har
    raise CoopCoepAuditError(
        f"scan_har_resources expects str/dict, got {type(har).__name__}"
    )


# ---------- combined audit --------------------------------------------

@dataclass
class IsolationReport:
    """Result of :func:`audit_isolation`."""

    page_url: str
    policy: PagePolicy
    isolated: bool
    resource_findings: List[ResourceFinding] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def passed(self) -> bool:
        return self.isolated and not self.resource_findings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_url": self.page_url,
            "policy": {
                "coop": self.policy.coop.value,
                "coep": self.policy.coep.value,
            },
            "isolated": self.isolated,
            "resource_findings": [asdict(f) for f in self.resource_findings],
            "notes": list(self.notes),
            "passed": self.passed(),
        }


def audit_isolation(
    page_url: str,
    page_headers: Iterable[Tuple[str, str]],
    *,
    har: Optional[Union[str, Dict[str, Any]]] = None,
) -> IsolationReport:
    """Combined page + resource audit. ``har`` is optional but recommended."""
    if not isinstance(page_url, str) or not page_url:
        raise CoopCoepAuditError("page_url must be non-empty string")
    policy = parse_page_headers(page_headers)
    isolated = policy.isolated()
    notes: List[str] = []
    if policy.coop != CoopValue.SAME_ORIGIN:
        notes.append(f"COOP is {policy.coop.value}, want same-origin")
    if policy.coep not in (CoepValue.REQUIRE_CORP, CoepValue.CREDENTIALLESS):
        notes.append(f"COEP is {policy.coep.value}, want require-corp/credentialless")
    resource_findings: List[ResourceFinding] = []
    if har is not None and policy.coep != CoepValue.UNSAFE_NONE:
        resource_findings = scan_har_resources(
            har, page_url=page_url, coep=policy.coep,
        )
    return IsolationReport(
        page_url=page_url,
        policy=policy,
        isolated=isolated,
        resource_findings=resource_findings,
        notes=notes,
    )


def assert_isolated(report: IsolationReport) -> None:
    if not isinstance(report, IsolationReport):
        raise CoopCoepAuditError("assert_isolated expects IsolationReport")
    if report.passed():
        return
    if not report.isolated:
        raise CoopCoepAuditError(
            f"not crossOriginIsolated: {', '.join(report.notes) or 'unknown reason'}"
        )
    bad = report.resource_findings[0]
    raise CoopCoepAuditError(
        f"resource violates COEP: {bad.url} ({bad.reason})"
    )
