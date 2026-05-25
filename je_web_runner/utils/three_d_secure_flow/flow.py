"""
3-D Secure 2.x flow path assertions.

A modern checkout has three branches depending on the card / issuer /
risk score:

* **Frictionless** — issuer returns ``transStatus=Y`` without any
  challenge UI; flow goes straight to confirmation.
* **Challenge** — issuer returns ``transStatus=C``; ACS iframe is
  rendered, the page must collect the user's OTP / biometric, and the
  ``cres`` value must be POSTed back.
* **Fallback / reject** — issuer returns ``transStatus=R`` or ``N``;
  page must show the right error and not finalize the order.

This module models a ``Flow`` value object that the page-driver fills
in as it walks through the checkout, plus assertions that verify the
right branch fired for the right input.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ThreeDSecureFlowError(WebRunnerException):
    """Raised when the captured 3DS flow violates an invariant."""


class TransStatus(str, Enum):
    AUTHENTICATED = "Y"          # frictionless approval
    NOT_AUTHENTICATED = "N"      # issuer says no
    CHALLENGE = "C"              # ACS challenge required
    REJECTED = "R"               # high risk, reject
    ATTEMPTED = "A"              # attempt-mode (no real auth)
    UNAVAILABLE = "U"            # ACS down


class Outcome(str, Enum):
    FRICTIONLESS_OK = "frictionless_ok"
    CHALLENGE_OK = "challenge_ok"
    REJECTED = "rejected"
    FALLBACK = "fallback"
    INCOMPLETE = "incomplete"


@dataclass
class Flow:
    """Snapshot of one checkout's 3DS journey."""

    pan_last4: str = ""
    trans_status: TransStatus = TransStatus.UNAVAILABLE
    challenge_shown: bool = False
    cres_submitted: bool = False
    error_displayed: str = ""
    order_finalized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.trans_status, TransStatus):
            raise ThreeDSecureFlowError(
                f"trans_status must be TransStatus, got {self.trans_status!r}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "trans_status": self.trans_status.value}


def classify(flow: Flow) -> Outcome:
    """Decide which branch this flow took."""
    s = flow.trans_status
    if s == TransStatus.AUTHENTICATED:
        if flow.challenge_shown or flow.cres_submitted:
            return Outcome.INCOMPLETE   # frictionless shouldn't show challenge
        return Outcome.FRICTIONLESS_OK if flow.order_finalized else Outcome.INCOMPLETE
    if s == TransStatus.CHALLENGE:
        if not flow.challenge_shown:
            return Outcome.INCOMPLETE
        if not flow.cres_submitted:
            return Outcome.INCOMPLETE
        return Outcome.CHALLENGE_OK if flow.order_finalized else Outcome.INCOMPLETE
    if s in (TransStatus.NOT_AUTHENTICATED, TransStatus.REJECTED):
        if flow.order_finalized:
            return Outcome.INCOMPLETE   # finalized despite reject = bug
        return Outcome.REJECTED
    if s in (TransStatus.ATTEMPTED, TransStatus.UNAVAILABLE):
        return Outcome.FALLBACK
    return Outcome.INCOMPLETE


def assert_outcome(flow: Flow, *, expected: Outcome) -> None:
    if not isinstance(expected, Outcome):
        raise ThreeDSecureFlowError(
            f"expected must be Outcome, got {type(expected).__name__}"
        )
    actual = classify(flow)
    if actual != expected:
        raise ThreeDSecureFlowError(
            f"flow outcome {actual.value!r} != expected {expected.value!r}; "
            f"flow={flow.to_dict()}"
        )


def assert_no_silent_finalize(flow: Flow) -> None:
    """A rejected card must NEVER finalize the order."""
    if flow.trans_status in (TransStatus.NOT_AUTHENTICATED, TransStatus.REJECTED) \
            and flow.order_finalized:
        raise ThreeDSecureFlowError(
            "order finalized despite trans_status="
            f"{flow.trans_status.value!r} (silent acceptance — PCI bug)"
        )


def assert_challenge_branch_complete(flow: Flow) -> None:
    """If we entered the challenge branch, both the iframe and the cres
    submission must have happened."""
    if flow.trans_status != TransStatus.CHALLENGE:
        return
    if not flow.challenge_shown:
        raise ThreeDSecureFlowError(
            "trans_status=C but ACS challenge iframe never shown"
        )
    if not flow.cres_submitted:
        raise ThreeDSecureFlowError(
            "ACS challenge iframe shown but cres never submitted "
            "(user could have closed the iframe and bypassed 3DS)"
        )


def assert_user_message_for(flow: Flow, *, contains: str) -> None:
    """For the reject branch the page should show a recognisable error."""
    if classify(flow) != Outcome.REJECTED:
        return
    if contains and contains not in flow.error_displayed:
        raise ThreeDSecureFlowError(
            f"rejected flow but error message {flow.error_displayed!r} "
            f"does not contain {contains!r}"
        )
