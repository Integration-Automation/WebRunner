"""
偵測 ``?redirect=`` / ``?next=`` / ``?return_to=`` 類參數的 open-redirect 弱點。
The classic phishing primitive: legitimate domain → user trusts the URL
→ click → server 302s to attacker.com. Hard to catch without explicit
testing.

This module:

1. Generates a payload set covering same-origin variants, scheme-relative
   (`//evil.com`), absolute external URLs, mixed-case bypass, path-only
   tricks (`/\\evil.com`), data: / javascript: schemes.
2. Given a callable that performs the request and returns the final
   Location header (without auto-following), classifies the result as
   ALLOWED (vulnerable), BLOCKED (safe), or AMBIGUOUS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Sequence
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class OpenRedirectError(WebRunnerException):
    """Raised on malformed inputs or invalid probe result."""


class ProbeOutcome(str, Enum):
    BLOCKED = "blocked"        # safe — redirect stayed same-origin or rejected
    ALLOWED = "allowed"        # vulnerable — went off-origin
    AMBIGUOUS = "ambiguous"    # unclear — neither rejected nor clearly off-origin


# ---------- payload generation -----------------------------------------

@dataclass(frozen=True)
class RedirectPayload:
    """One probe value to inject into the redirect parameter."""

    label: str
    value: str
    expected_off_origin_host: str | None = None


def default_payloads(attacker_host: str = "evil.example") -> list[RedirectPayload]:
    """Return a representative payload set for the given attacker host."""
    if not isinstance(attacker_host, str) or "." not in attacker_host:
        raise OpenRedirectError("attacker_host must look like a domain")
    return [
        # S5332 ok: these payloads INTENTIONALLY use http:// — the whole point
        # of an open-redirect probe is to see if the app redirects to them.
        RedirectPayload("absolute_http",
                        f"http://{attacker_host}/",
                        attacker_host),
        RedirectPayload("absolute_https",
                        f"https://{attacker_host}/",
                        attacker_host),
        RedirectPayload("scheme_relative",
                        f"//{attacker_host}/",
                        attacker_host),
        RedirectPayload("backslash_bypass",
                        f"/\\\\{attacker_host}/",
                        attacker_host),
        RedirectPayload("mixed_case",
                        f"HtTpS://{attacker_host}/",
                        attacker_host),
        RedirectPayload("at_sign_userinfo",
                        f"https://trusted.com@{attacker_host}/",
                        attacker_host),
        RedirectPayload("data_uri",
                        "data:text/html,<script>alert(1)</script>",
                        None),
        RedirectPayload("javascript_uri",
                        "javascript:alert(1)",
                        None),
    ]


# ---------- classification ---------------------------------------------

@dataclass
class ProbeResult:
    """One payload → one outcome."""

    payload: RedirectPayload
    final_location: str | None
    status_code: int
    outcome: ProbeOutcome
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload_label": self.payload.label,
            "payload_value": self.payload.value,
            "final_location": self.final_location,
            "status_code": self.status_code,
            "outcome": self.outcome.value,
            "note": self.note,
        }


def classify_response(
    payload: RedirectPayload,
    final_location: str | None,
    status_code: int,
    *,
    legitimate_host: str,
) -> ProbeResult:
    """Decide if the response indicates an open redirect."""
    if not isinstance(legitimate_host, str) or not legitimate_host:
        raise OpenRedirectError("legitimate_host must be non-empty string")
    if not isinstance(status_code, int):
        raise OpenRedirectError("status_code must be int")
    if status_code < 300 or status_code >= 400:
        return ProbeResult(
            payload=payload,
            final_location=final_location,
            status_code=status_code,
            outcome=ProbeOutcome.BLOCKED,
            note=f"non-redirect status {status_code}",
        )
    if not final_location:
        return ProbeResult(
            payload=payload,
            final_location=None,
            status_code=status_code,
            outcome=ProbeOutcome.AMBIGUOUS,
            note="redirect status with empty Location",
        )
    scheme, host = _parse_target(final_location)
    if scheme in ("javascript", "data"):
        return ProbeResult(
            payload=payload,
            final_location=final_location,
            status_code=status_code,
            outcome=ProbeOutcome.ALLOWED,
            note=f"redirected to {scheme}: scheme",
        )
    if host and not _is_same_host(host, legitimate_host):
        return ProbeResult(
            payload=payload,
            final_location=final_location,
            status_code=status_code,
            outcome=ProbeOutcome.ALLOWED,
            note=f"redirected to {host}",
        )
    return ProbeResult(
        payload=payload,
        final_location=final_location,
        status_code=status_code,
        outcome=ProbeOutcome.BLOCKED,
    )


def _parse_target(location: str) -> tuple:
    if location.startswith("//"):
        parsed = urlparse(f"http:{location}")
        return "http", (parsed.hostname or "").lower()
    try:
        parsed = urlparse(location)
    except ValueError:
        return "", ""
    return parsed.scheme.lower(), (parsed.hostname or "").lower()


def _is_same_host(actual: str, legitimate: str) -> bool:
    actual = actual.lower()
    legitimate = legitimate.lower()
    if actual == legitimate:
        return True
    return actual.endswith("." + legitimate)


# ---------- probe driver ------------------------------------------------

ProbeFn = Callable[[str], "ProbeResponse"]


@dataclass(frozen=True)
class ProbeResponse:
    """What the probe callable must return."""

    status_code: int
    location: str | None


@dataclass
class ProbeReport:
    """Aggregate over all payloads."""

    legitimate_host: str
    results: list[ProbeResult] = field(default_factory=list)

    def vulnerable(self) -> list[ProbeResult]:
        return [r for r in self.results if r.outcome == ProbeOutcome.ALLOWED]

    def passed(self) -> bool:
        return not self.vulnerable()


def probe_all(
    payloads: Sequence[RedirectPayload],
    probe: ProbeFn,
    *,
    legitimate_host: str,
) -> ProbeReport:
    """Drive ``probe`` once per payload, classify, return report."""
    if not payloads:
        raise OpenRedirectError("payloads must be non-empty")
    if not callable(probe):
        raise OpenRedirectError("probe must be callable")
    report = ProbeReport(legitimate_host=legitimate_host)
    for payload in payloads:
        try:
            response = probe(payload.value)
        except Exception as error:
            raise OpenRedirectError(
                f"probe failed for {payload.label!r}: {error!r}"
            ) from error
        if not isinstance(response, ProbeResponse):
            raise OpenRedirectError(
                f"probe must return ProbeResponse, got {type(response).__name__}"
            )
        report.results.append(classify_response(
            payload, response.location, response.status_code,
            legitimate_host=legitimate_host,
        ))
    return report


# ---------- assertion --------------------------------------------------

def assert_safe(report: ProbeReport) -> None:
    """Raise if any payload was classified ALLOWED."""
    if not isinstance(report, ProbeReport):
        raise OpenRedirectError("assert_safe expects ProbeReport")
    if report.passed():
        return
    labels = ", ".join(r.payload.label for r in report.vulnerable())
    raise OpenRedirectError(
        f"open redirect vulnerable to: {labels}"
    )
