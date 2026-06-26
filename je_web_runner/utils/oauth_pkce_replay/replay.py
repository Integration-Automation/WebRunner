"""
重放 OAuth state / PKCE code_verifier,確認 authorization server 真的拒
絕——而不是 silently issue 一個新 token。
Common bugs this catches:

* Authorization server accepts the same ``state`` twice (CSRF protection
  is theatrical).
* PKCE ``code_verifier`` reuse is accepted (downgrade to no-PKCE).
* Stale ``authorization_code`` still works after first redemption.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class OauthPkceReplayError(WebRunnerException):
    """Raised on probe failure or replay-accepted regression."""


class ReplayOutcome(str, Enum):
    REJECTED = "rejected"           # server returned an error → good
    ACCEPTED = "accepted"           # server issued a token → BUG
    AMBIGUOUS = "ambiguous"         # unexpected status / network issue


# ---------- PKCE helpers -----------------------------------------------

def generate_verifier(length: int = 64) -> str:
    """Generate a fresh PKCE ``code_verifier`` (43–128 chars per RFC 7636)."""
    if not 43 <= length <= 128:
        raise OauthPkceReplayError("verifier length must be in [43, 128]")
    # nosec B311 — used to *generate* test verifiers, NOT a security primitive
    # for the SUT (which has its own PKCE implementation). secrets.token_urlsafe
    # is fine for this auxiliary purpose.
    return secrets.token_urlsafe(length)[:length]


def challenge_for(verifier: str) -> str:
    """S256 challenge derivation per RFC 7636."""
    if not isinstance(verifier, str) or not verifier:
        raise OauthPkceReplayError("verifier must be non-empty string")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ---------- probe model ------------------------------------------------

@dataclass
class TokenExchangeResponse:
    """What the probe callable must return."""

    status_code: int
    body: dict[str, Any]


ProbeFn = Callable[[dict[str, Any]], TokenExchangeResponse]
"""Callable that POSTs to the token endpoint with the given payload."""


@dataclass
class ReplayCase:
    """One attempt at re-using a previously-consumed value."""

    name: str
    payload: dict[str, Any]
    expected: ReplayOutcome = ReplayOutcome.REJECTED


@dataclass
class ReplayResult:
    case: str
    outcome: ReplayOutcome
    status_code: int
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "outcome": self.outcome.value}


def _classify(response: TokenExchangeResponse) -> ReplayOutcome:
    if response.status_code >= 500:
        return ReplayOutcome.AMBIGUOUS
    body = response.body if isinstance(response.body, dict) else {}
    if "access_token" in body:
        return ReplayOutcome.ACCEPTED
    if response.status_code in (400, 401, 403):
        return ReplayOutcome.REJECTED
    return ReplayOutcome.AMBIGUOUS


def replay(case: ReplayCase, probe: ProbeFn) -> ReplayResult:
    """Send the case payload via ``probe`` and classify."""
    if not isinstance(case, ReplayCase):
        raise OauthPkceReplayError("case must be ReplayCase")
    if not callable(probe):
        raise OauthPkceReplayError("probe must be callable")
    try:
        response = probe(case.payload)
    except Exception as error:
        raise OauthPkceReplayError(
            f"probe failed for {case.name!r}: {error!r}"
        ) from error
    if not isinstance(response, TokenExchangeResponse):
        raise OauthPkceReplayError(
            f"probe must return TokenExchangeResponse, got {type(response).__name__}"
        )
    outcome = _classify(response)
    return ReplayResult(
        case=case.name, outcome=outcome,
        status_code=response.status_code,
        note=(
            f"expected {case.expected.value}, got {outcome.value}"
            if outcome != case.expected else ""
        ),
    )


def run_cases(cases: Sequence[ReplayCase], probe: ProbeFn) -> list[ReplayResult]:
    if not cases:
        raise OauthPkceReplayError("cases must be non-empty")
    return [replay(c, probe) for c in cases]


def assert_all_rejected(results: Sequence[ReplayResult]) -> None:
    """Raise if any result is ACCEPTED (the server reused something it shouldn't)."""
    accepted = [r for r in results if r.outcome == ReplayOutcome.ACCEPTED]
    if accepted:
        names = [r.case for r in accepted]
        raise OauthPkceReplayError(
            f"server accepted replay for: {names}"
        )
