"""
CHIPS (Cookies Having Independent Partitioned State) compliance auditor.

Third-party iframes & ad-tech increasingly need ``Partitioned`` cookies
for cross-site embedding. This module audits a HAR (or list of
``Set-Cookie`` headers) and flags:

* Third-party cookies missing ``Partitioned``.
* ``Partitioned`` without ``Secure`` (browsers reject these).
* ``Partitioned`` with ``SameSite=Lax/Strict`` (must be ``None``).
* First-party cookies that *unnecessarily* set ``Partitioned``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CookieChipsAuditError(WebRunnerException):
    """Raised when input is malformed."""


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class SetCookie:
    name: str
    value: str = ""
    attributes: Dict[str, Optional[str]] = field(default_factory=dict)

    @property
    def is_partitioned(self) -> bool:
        return "partitioned" in self.attributes

    @property
    def is_secure(self) -> bool:
        return "secure" in self.attributes

    @property
    def samesite(self) -> str:
        v = self.attributes.get("samesite") or ""
        return v.lower()


def parse_set_cookie(header: str) -> SetCookie:
    """Parse a single ``Set-Cookie`` header value."""
    if not isinstance(header, str) or "=" not in header.split(";", 1)[0]:
        raise CookieChipsAuditError(f"invalid Set-Cookie header: {header!r}")
    parts = [p.strip() for p in header.split(";")]
    name, _, value = parts[0].partition("=")
    attrs: Dict[str, Optional[str]] = {}
    for part in parts[1:]:
        if not part:
            continue
        if "=" in part:
            k, _, v = part.partition("=")
            attrs[k.strip().lower()] = v.strip()
        else:
            attrs[part.strip().lower()] = None
    return SetCookie(name=name.strip(), value=value.strip(), attributes=attrs)


@dataclass
class Finding:
    severity: Severity
    rule: str
    cookie: str
    page_origin: str
    cookie_origin: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "severity": self.severity.value}


def _registrable(host: str) -> str:
    """Crude eTLD+1 — good enough for tests; production should use PSL."""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def _is_third_party(page_url: str, cookie_url: str) -> bool:
    p = urlparse(page_url).hostname or ""
    c = urlparse(cookie_url).hostname or ""
    return bool(p) and bool(c) and _registrable(p) != _registrable(c)


def _check_cookie(  # noqa: PLR0912 — flat rule chain, kept linear on purpose
    cookie: SetCookie,
    page_url: str,
    cookie_url: str,
) -> List[Finding]:
    third_party = _is_third_party(page_url, cookie_url)
    out: List[Finding] = []
    common = dict(
        cookie=cookie.name,
        page_origin=urlparse(page_url).netloc,
        cookie_origin=urlparse(cookie_url).netloc,
    )
    if cookie.is_partitioned:
        if not cookie.is_secure:
            out.append(Finding(
                severity=Severity.ERROR, rule="partitioned-requires-secure",
                message="Partitioned cookie missing Secure (browser will reject).",
                **common,
            ))
        if cookie.samesite != "none":
            out.append(Finding(
                severity=Severity.ERROR, rule="partitioned-requires-samesite-none",
                message=f"Partitioned cookie has SameSite={cookie.samesite or 'unset'} (must be None).",
                **common,
            ))
        if not third_party:
            out.append(Finding(
                severity=Severity.WARN, rule="partitioned-on-first-party",
                message="First-party cookie sets Partitioned — likely unnecessary.",
                **common,
            ))
    elif third_party:
        out.append(Finding(
            severity=Severity.ERROR, rule="third-party-missing-partitioned",
            message="Third-party cookie without Partitioned will be blocked.",
            **common,
        ))
    return out


def audit_har(har: Dict[str, Any], page_url: str) -> List[Finding]:
    """Walk a HAR's responses and emit findings for every Set-Cookie header."""
    if not isinstance(har, dict):
        raise CookieChipsAuditError("har must be a dict")
    if not isinstance(page_url, str) or not page_url:
        raise CookieChipsAuditError("page_url must be non-empty string")
    entries = har.get("log", {}).get("entries", [])
    if not isinstance(entries, list):
        raise CookieChipsAuditError("har.log.entries must be a list")
    findings: List[Finding] = []
    for entry in entries:
        request_url = (entry.get("request") or {}).get("url", "")
        headers = (entry.get("response") or {}).get("headers", []) or []
        for header in headers:
            if (header.get("name") or "").lower() != "set-cookie":
                continue
            try:
                cookie = parse_set_cookie(header.get("value", ""))
            except CookieChipsAuditError:
                continue
            findings.extend(_check_cookie(cookie, page_url, request_url))
    return findings


def audit_headers(
    headers: Iterable[str], page_url: str, cookie_url: str,
) -> List[Finding]:
    findings: List[Finding] = []
    for header in headers:
        try:
            cookie = parse_set_cookie(header)
        except CookieChipsAuditError:
            continue
        findings.extend(_check_cookie(cookie, page_url, cookie_url))
    return findings


def assert_no_errors(findings: Iterable[Finding]) -> None:
    errors = [f for f in findings if f.severity == Severity.ERROR]
    if errors:
        names = [f"{f.cookie}({f.rule})" for f in errors]
        raise CookieChipsAuditError(
            f"CHIPS audit errors: {names}"
        )
