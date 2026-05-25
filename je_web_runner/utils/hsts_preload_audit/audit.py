"""
HSTS preload list compliance auditor.

To qualify for the Chrome HSTS preload list (and by extension Firefox,
Safari, Edge), a site's ``Strict-Transport-Security`` header must:

* include ``max-age`` of at least one year (31_536_000 seconds);
* include the ``includeSubDomains`` directive;
* include the ``preload`` directive;
* be served from an HTTPS response on the apex domain.

This module parses an HSTS header and verifies all four conditions.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class HstsPreloadAuditError(WebRunnerException):
    """Raised when a site does not meet HSTS preload criteria."""


PRELOAD_MIN_MAX_AGE = 31_536_000   # 1 year, per https://hstspreload.org


@dataclass
class HstsHeader:
    raw: str
    max_age: int = 0
    include_subdomains: bool = False
    preload: bool = False


def parse_header(value: str) -> HstsHeader:
    if not isinstance(value, str) or not value.strip():
        raise HstsPreloadAuditError("HSTS header value must be non-empty")
    out = HstsHeader(raw=value)
    for part in value.split(";"):
        token = part.strip().lower()
        if not token:
            continue
        if token.startswith("max-age"):
            match = re.match(r"max-age\s*=\s*(\d+)", token)
            if not match:
                raise HstsPreloadAuditError(
                    f"unparseable max-age: {token!r}"
                )
            out.max_age = int(match.group(1))
        elif token == "includesubdomains":
            out.include_subdomains = True
        elif token == "preload":
            out.preload = True
    return out


def assert_preload_ready(header: HstsHeader) -> None:
    problems = []
    if header.max_age < PRELOAD_MIN_MAX_AGE:
        problems.append(
            f"max-age={header.max_age} < {PRELOAD_MIN_MAX_AGE}"
        )
    if not header.include_subdomains:
        problems.append("missing includeSubDomains")
    if not header.preload:
        problems.append("missing preload directive")
    if problems:
        raise HstsPreloadAuditError(
            f"HSTS header does not meet preload criteria: {problems}"
        )


def assert_served_over_https(scheme: str) -> None:
    if not isinstance(scheme, str):
        raise HstsPreloadAuditError("scheme must be a string")
    if scheme.lower() != "https":
        raise HstsPreloadAuditError(
            f"HSTS header served over {scheme!r} — must be HTTPS to be honoured"
        )
