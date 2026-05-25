"""
Webhook signature verifier covering the common providers.

Receivers are notoriously easy to misconfigure (wrong secret env-var,
missing replay-window check). This module gives tests a single helper
to confirm a captured webhook body **would** have been accepted by the
verifier — and also lets you negative-test that tampered bodies are
rejected.

Supported schemes (signed-payload pattern):

* **GitHub** ``X-Hub-Signature-256`` — ``sha256=<HMAC-SHA256(secret, body)>``
* **Stripe** ``Stripe-Signature`` — ``t=<ts>,v1=<HMAC-SHA256(secret, t.body)>``
* **Slack** ``X-Slack-Signature`` — ``v0=<HMAC-SHA256(secret, "v0:"+ts+":"+body)>``
* **Generic** ``X-Signature`` — ``HMAC-SHA256(secret, body)`` (hex).
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebhookSignatureVerifyError(WebRunnerException):
    """Raised when a webhook signature fails verification."""


_GITHUB_SIG_PREFIX = "sha256="


class Scheme(str, Enum):
    GITHUB = "github"
    STRIPE = "stripe"
    SLACK = "slack"
    GENERIC = "generic"


@dataclass
class VerifyResult:
    ok: bool
    scheme: Scheme
    note: str = ""


def _equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("ascii"), b.encode("ascii"))


def _hex(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _verify_github(headers: Mapping[str, str], body: bytes,
                   secret: str) -> VerifyResult:
    received = headers.get("X-Hub-Signature-256")
    if not received:
        raise WebhookSignatureVerifyError("missing X-Hub-Signature-256 header")
    if not received.startswith(_GITHUB_SIG_PREFIX):
        raise WebhookSignatureVerifyError(
            "X-Hub-Signature-256 must start with 'sha256='"
        )
    expected = _GITHUB_SIG_PREFIX + _hex(secret, body)
    return VerifyResult(ok=_equal(expected, received), scheme=Scheme.GITHUB)


def _verify_stripe(headers: Mapping[str, str], body: bytes, secret: str,
                   tolerance_seconds: int) -> VerifyResult:
    raw = headers.get("Stripe-Signature")
    if not raw:
        raise WebhookSignatureVerifyError("missing Stripe-Signature header")
    parts = {p.split("=", 1)[0]: p.split("=", 1)[1]
             for p in raw.split(",") if "=" in p}
    t = parts.get("t")
    v1 = parts.get("v1")
    if not t or not v1:
        raise WebhookSignatureVerifyError(
            "Stripe-Signature missing t or v1 component"
        )
    try:
        ts = int(t)
    except ValueError as exc:
        raise WebhookSignatureVerifyError(
            f"Stripe timestamp not numeric: {t!r}"
        ) from exc
    if abs(time.time() - ts) > tolerance_seconds:
        raise WebhookSignatureVerifyError(
            f"Stripe timestamp {ts} outside tolerance "
            f"({tolerance_seconds}s) — replay attack defence"
        )
    signed = f"{t}.".encode("utf-8") + body
    expected = _hex(secret, signed)
    return VerifyResult(ok=_equal(expected, v1), scheme=Scheme.STRIPE)


def _verify_slack(headers: Mapping[str, str], body: bytes, secret: str,
                  tolerance_seconds: int) -> VerifyResult:
    sig = headers.get("X-Slack-Signature")
    ts = headers.get("X-Slack-Request-Timestamp")
    if not sig or not ts:
        raise WebhookSignatureVerifyError(
            "missing X-Slack-Signature or X-Slack-Request-Timestamp header"
        )
    try:
        ts_int = int(ts)
    except ValueError as exc:
        raise WebhookSignatureVerifyError(
            f"Slack timestamp not numeric: {ts!r}"
        ) from exc
    if abs(time.time() - ts_int) > tolerance_seconds:
        raise WebhookSignatureVerifyError(
            f"Slack timestamp {ts_int} outside tolerance ({tolerance_seconds}s)"
        )
    base = f"v0:{ts}:".encode("utf-8") + body
    expected = "v0=" + _hex(secret, base)
    return VerifyResult(ok=_equal(expected, sig), scheme=Scheme.SLACK)


def _verify_generic(headers: Mapping[str, str], body: bytes,
                    secret: str) -> VerifyResult:
    received = headers.get("X-Signature")
    if not received:
        raise WebhookSignatureVerifyError("missing X-Signature header")
    return VerifyResult(ok=_equal(_hex(secret, body), received.lower()),
                        scheme=Scheme.GENERIC)


def verify(
    scheme: Scheme,
    headers: Mapping[str, str],
    body: bytes,
    secret: str,
    tolerance_seconds: int = 300,
) -> VerifyResult:
    """Return a ``VerifyResult`` (raises only on malformed input)."""
    if not isinstance(scheme, Scheme):
        raise WebhookSignatureVerifyError(
            f"scheme must be Scheme, got {type(scheme).__name__}"
        )
    if not isinstance(headers, Mapping):
        raise WebhookSignatureVerifyError("headers must be a mapping")
    if not isinstance(body, (bytes, bytearray)):
        raise WebhookSignatureVerifyError("body must be bytes")
    if not isinstance(secret, str) or not secret:
        raise WebhookSignatureVerifyError("secret must be non-empty string")
    if scheme == Scheme.GITHUB:
        return _verify_github(headers, bytes(body), secret)
    if scheme == Scheme.STRIPE:
        return _verify_stripe(headers, bytes(body), secret, tolerance_seconds)
    if scheme == Scheme.SLACK:
        return _verify_slack(headers, bytes(body), secret, tolerance_seconds)
    return _verify_generic(headers, bytes(body), secret)


def assert_valid(result: VerifyResult) -> None:
    if not result.ok:
        raise WebhookSignatureVerifyError(
            f"signature failed verification for {result.scheme.value}"
            + (f" — {result.note}" if result.note else "")
        )


# ----------- helper for tests: produce a signature for a body --------

def sign_github(body: bytes, secret: str) -> str:
    return _GITHUB_SIG_PREFIX + _hex(secret, body)


def sign_stripe(body: bytes, secret: str, ts: Optional[int] = None) -> str:
    ts = int(ts or time.time())
    signed = f"{ts}.".encode("utf-8") + body
    return f"t={ts},v1={_hex(secret, signed)}"


def sign_slack(body: bytes, secret: str, ts: Optional[int] = None) -> str:
    ts = int(ts or time.time())
    base = f"v0:{ts}:".encode("utf-8") + body
    return "v0=" + _hex(secret, base)
