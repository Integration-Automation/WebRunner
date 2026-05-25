"""
完整 ``verb × origin × credentials`` CORS preflight + simple-request 矩陣探測。
Most apps test the 1-2 common CORS combos and miss edge cases:
``OPTIONS`` with ``Authorization`` header, credentialed ``DELETE`` from
a subdomain, ``Origin: null`` (file://, sandboxed iframes), etc.

This module:

1. Builds the request matrix (default = all combinations).
2. Hands each ``(verb, origin, with_credentials)`` triplet to a
   user-supplied probe callable.
3. Classifies the response as ALLOWED / BLOCKED / AMBIGUOUS.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from itertools import product
from typing import Any, Callable, Dict, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CorsMatrixError(WebRunnerException):
    """Raised on bad inputs or probe failure."""


class CorsOutcome(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    AMBIGUOUS = "ambiguous"


_PREFLIGHT_VERBS = {"PUT", "PATCH", "DELETE"}


# ---------- matrix ------------------------------------------------------

@dataclass(frozen=True)
class CorsCase:
    """One row of the matrix."""

    verb: str
    origin: str
    with_credentials: bool

    def needs_preflight(self) -> bool:
        return self.verb.upper() in _PREFLIGHT_VERBS


def build_matrix(
    *,
    verbs: Sequence[str] = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"),
    origins: Sequence[str] = (
        "https://app.example",      # same-org subdomain
        "https://other.example",    # cross-origin
        "null",                     # sandboxed iframe / data:
    ),
    credentials_modes: Sequence[bool] = (False, True),
) -> List[CorsCase]:
    """Cartesian product of the matrix axes."""
    if not verbs:
        raise CorsMatrixError("verbs must be non-empty")
    if not origins:
        raise CorsMatrixError("origins must be non-empty")
    if not credentials_modes:
        raise CorsMatrixError("credentials_modes must be non-empty")
    return [
        CorsCase(verb=v.upper(), origin=o, with_credentials=c)
        for v, o, c in product(verbs, origins, credentials_modes)
    ]


# ---------- probe / classify -------------------------------------------

@dataclass
class CorsResponse:
    """What the probe callable must return."""

    status_code: int
    allow_origin: Optional[str]
    allow_credentials: bool = False
    allow_methods: Sequence[str] = ()
    allow_headers: Sequence[str] = ()


@dataclass
class CorsResult:
    """Per-case outcome."""

    case: CorsCase
    outcome: CorsOutcome
    response: CorsResponse
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case": asdict(self.case),
            "outcome": self.outcome.value,
            "response": asdict(self.response),
            "note": self.note,
        }


def classify(case: CorsCase, response: CorsResponse) -> CorsResult:
    """Apply standard CORS rules to decide allowed/blocked/ambiguous."""
    if not isinstance(response, CorsResponse):
        raise CorsMatrixError("response must be CorsResponse")
    if response.status_code >= 500:
        return CorsResult(case=case, outcome=CorsOutcome.AMBIGUOUS,
                          response=response, note=f"server error {response.status_code}")
    origin_ok = (
        response.allow_origin == "*"
        or response.allow_origin == case.origin
        or (case.origin == "null" and response.allow_origin == "null")
    )
    if case.with_credentials:
        # Spec: cannot combine ACAO=* with credentials.
        if response.allow_origin == "*":
            return CorsResult(case=case, outcome=CorsOutcome.BLOCKED,
                              response=response, note="ACAO=* incompatible with credentials")
        if not response.allow_credentials:
            return CorsResult(case=case, outcome=CorsOutcome.BLOCKED,
                              response=response, note="ACA-Credentials missing/false")
    if not origin_ok:
        return CorsResult(case=case, outcome=CorsOutcome.BLOCKED,
                          response=response,
                          note=f"origin {case.origin} not in ACAO {response.allow_origin}")
    if case.needs_preflight() and case.verb.upper() not in (m.upper() for m in response.allow_methods):
        return CorsResult(case=case, outcome=CorsOutcome.BLOCKED,
                          response=response,
                          note=f"verb {case.verb} missing from ACA-Methods")
    return CorsResult(case=case, outcome=CorsOutcome.ALLOWED, response=response)


ProbeFn = Callable[[CorsCase], CorsResponse]


def run_matrix(
    cases: Sequence[CorsCase], probe: ProbeFn,
) -> List[CorsResult]:
    """Drive ``probe`` once per case and classify the response."""
    if not cases:
        raise CorsMatrixError("cases must be non-empty")
    if not callable(probe):
        raise CorsMatrixError("probe must be callable")
    out: List[CorsResult] = []
    for case in cases:
        try:
            response = probe(case)
        except Exception as error:
            raise CorsMatrixError(
                f"probe failed for {case}: {error!r}"
            ) from error
        out.append(classify(case, response))
    return out


# ---------- assertions --------------------------------------------------

def assert_origin_blocked(
    results: Sequence[CorsResult], *, origin: str,
) -> None:
    """Assert every result for ``origin`` is BLOCKED (origin must NOT be allow-listed)."""
    leaked = [
        r for r in results
        if r.case.origin == origin and r.outcome == CorsOutcome.ALLOWED
    ]
    if leaked:
        verbs = sorted({r.case.verb for r in leaked})
        raise CorsMatrixError(
            f"origin {origin!r} unexpectedly allowed for verbs: {verbs}"
        )


def assert_credentials_require_explicit_origin(
    results: Sequence[CorsResult],
) -> None:
    """Assert no result combines ACAO=* with credentials=true."""
    bad = [
        r for r in results
        if r.case.with_credentials and r.response.allow_origin == "*"
    ]
    if bad:
        raise CorsMatrixError(
            f"{len(bad)} responses returned ACAO=* with credentials — spec violation"
        )
