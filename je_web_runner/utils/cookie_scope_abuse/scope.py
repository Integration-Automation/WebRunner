"""
Cookie domain / path scope abuse detection.

Catches sloppy cookie config where:

* A session cookie is set on the apex domain (``Domain=.example.com``)
  instead of the marketing subdomain — exposes the session to XSS in
  blog.example.com.
* A high-value cookie has ``Path=/`` instead of ``Path=/api``.
* The cookie lacks ``HttpOnly`` / ``Secure`` / ``SameSite=Strict|Lax``
  but stores something session-shaped (>= 20 chars, alphanumeric).
* Cookie name suggests session/auth (``sid`` / ``session`` / ``token`` /
  ``jwt``) and one of the above is true.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CookieScopeAbuseError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class CookieScopeFinding:
    severity: Severity
    rule: str
    cookie: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "severity": self.severity.value}


_SESSION_LIKE_NAMES = re.compile(
    r"(?:^|[_-])(sid|session|token|jwt|auth)(?:[_-]|$)", re.IGNORECASE,
)
_SESSION_LIKE_VALUE = re.compile(r"^[A-Za-z0-9._-]{20,}$")


def _looks_like_session(name: str, value: str) -> bool:
    if _SESSION_LIKE_NAMES.search(name):
        return True
    return bool(_SESSION_LIKE_VALUE.match(value or ""))


def audit_cookie(
    cookie: Dict[str, Any], *, page_host: str,
) -> List[CookieScopeFinding]:
    if not isinstance(cookie, dict):
        raise CookieScopeAbuseError("cookie must be a dict")
    if not isinstance(page_host, str) or not page_host:
        raise CookieScopeAbuseError("page_host must be non-empty")
    name = str(cookie.get("name") or "")
    value = str(cookie.get("value") or "")
    domain = str(cookie.get("domain") or "").lstrip(".")
    path = str(cookie.get("path") or "/")
    http_only = bool(cookie.get("httpOnly") or cookie.get("http_only"))
    secure = bool(cookie.get("secure"))
    same_site = (cookie.get("sameSite") or cookie.get("same_site") or "").lower()
    findings: List[CookieScopeFinding] = []
    session_like = _looks_like_session(name, value)
    if session_like:
        page_apex = ".".join(page_host.split(".")[-2:])
        cookie_apex = ".".join(domain.split(".")[-2:]) if domain else page_apex
        if domain and domain != page_host and cookie_apex == page_apex:
            findings.append(CookieScopeFinding(
                severity=Severity.WARN, rule="session-on-apex",
                cookie=name,
                message=f"session-like cookie {name!r} scoped to apex "
                        f"{domain!r} — leaks to every subdomain",
            ))
        if path == "/":
            findings.append(CookieScopeFinding(
                severity=Severity.INFO, rule="session-path-root",
                cookie=name,
                message=f"session-like cookie {name!r} uses Path=/ — "
                        "narrow to /api or /auth if possible",
            ))
        if not http_only:
            findings.append(CookieScopeFinding(
                severity=Severity.ERROR, rule="session-no-httponly",
                cookie=name,
                message=f"session-like cookie {name!r} missing HttpOnly — "
                        "JS can read it (XSS risk)",
            ))
        if not secure:
            findings.append(CookieScopeFinding(
                severity=Severity.ERROR, rule="session-no-secure",
                cookie=name,
                message=f"session-like cookie {name!r} missing Secure — "
                        "leaks over plain HTTP",
            ))
        if same_site not in ("strict", "lax"):
            findings.append(CookieScopeFinding(
                severity=Severity.ERROR, rule="session-bad-samesite",
                cookie=name,
                message=f"session-like cookie {name!r} uses SameSite="
                        f"{same_site or 'unset'!r} — CSRF risk",
            ))
    return findings


def audit_many(
    cookies: Iterable[Dict[str, Any]], *, page_host: str,
) -> List[CookieScopeFinding]:
    out: List[CookieScopeFinding] = []
    for c in cookies:
        out.extend(audit_cookie(c, page_host=page_host))
    return out


def assert_no_errors(findings: Iterable[CookieScopeFinding]) -> None:
    errors = [f for f in findings if f.severity == Severity.ERROR]
    if errors:
        details = [f"{f.cookie}({f.rule})" for f in errors]
        raise CookieScopeAbuseError(
            f"{len(errors)} cookie scope error(s): {details}"
        )
