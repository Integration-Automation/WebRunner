"""
同一個請求送兩次,結果應相同(訂單 / 付款 / `POST /transfer` 最常見 bug)。
Strategy: caller supplies a "request runner" callable. We invoke it
twice (optionally with the same ``Idempotency-Key`` header), then
compare the two :class:`IdemResponse` records on three axes:

* status code & body shape
* state mutation (an optional state-probe callable)
* side-effect count (downstream rows / webhooks / emails)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class IdempotencyCheckError(WebRunnerException):
    """Raised on bad inputs or detected non-idempotency."""


# ---------- model ------------------------------------------------------

@dataclass
class IdemResponse:
    """Snapshot of one request's response."""

    status_code: int
    body: Any
    side_effect_count: int = 0

    def body_hash(self) -> str:
        try:
            serialised = json.dumps(self.body, sort_keys=True, default=str)
        except (TypeError, ValueError):
            serialised = repr(self.body)
        return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


@dataclass
class IdempotencyReport:
    """Outcome of :func:`check`."""

    first: IdemResponse
    second: IdemResponse
    state_before_first: Any | None = None
    state_after_first: Any | None = None
    state_after_second: Any | None = None
    violations: list[str] = field(default_factory=list)

    def passed(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        return {
            "first": asdict(self.first),
            "second": asdict(self.second),
            "state_before_first": self.state_before_first,
            "state_after_first": self.state_after_first,
            "state_after_second": self.state_after_second,
            "violations": list(self.violations),
            "passed": self.passed(),
        }


# ---------- check ------------------------------------------------------

RequestRunner = Callable[[], IdemResponse]
StateProbe = Callable[[], Any]


def check(
    request_runner: RequestRunner,
    *,
    state_probe: StateProbe | None = None,
    allow_status_change_to: Sequence[int] | None = None,
    ignore_body_keys: Sequence[str] = (),
) -> IdempotencyReport:
    """
    Run twice + compare. ``allow_status_change_to`` covers servers that
    legitimately return 409 / 304 on the second attempt (Stripe-style).
    ``ignore_body_keys`` is for non-deterministic fields (timestamps,
    request_id) the caller knows to ignore.
    """
    if not callable(request_runner):
        raise IdempotencyCheckError("request_runner must be callable")
    if state_probe is not None and not callable(state_probe):
        raise IdempotencyCheckError("state_probe must be callable")
    allowed = set(allow_status_change_to or ())
    ignored = set(ignore_body_keys)

    state_before = state_probe() if state_probe else None
    first = _safe_call(request_runner, "first")
    state_after_first = state_probe() if state_probe else None
    second = _safe_call(request_runner, "second")
    state_after_second = state_probe() if state_probe else None

    violations: list[str] = []
    if (
        first.status_code != second.status_code
        and second.status_code not in allowed
    ):
        violations.append(
            f"status changed {first.status_code} -> {second.status_code}"
        )
    if not _bodies_equal(first.body, second.body, ignored):
        violations.append("response body differs between calls")
    if (
        state_probe is not None
        and state_after_first != state_after_second
    ):
        violations.append("state changed between first and second call")
    if first.side_effect_count != second.side_effect_count:
        delta = abs(first.side_effect_count - second.side_effect_count)
        violations.append(
            f"side effect count differs (delta={delta})"
        )
    return IdempotencyReport(
        first=first, second=second,
        state_before_first=state_before,
        state_after_first=state_after_first,
        state_after_second=state_after_second,
        violations=violations,
    )


def _safe_call(runner: RequestRunner, label: str) -> IdemResponse:
    try:
        result = runner()
    except Exception as error:
        raise IdempotencyCheckError(
            f"{label} request raised: {error!r}"
        ) from error
    if not isinstance(result, IdemResponse):
        raise IdempotencyCheckError(
            f"runner must return IdemResponse, got {type(result).__name__}"
        )
    return result


def _strip_keys(payload: Any, ignored: set) -> Any:
    if isinstance(payload, dict):
        return {
            k: _strip_keys(v, ignored)
            for k, v in payload.items() if k not in ignored
        }
    if isinstance(payload, list):
        return [_strip_keys(v, ignored) for v in payload]
    return payload


def _bodies_equal(a: Any, b: Any, ignored: set) -> bool:
    return _strip_keys(a, ignored) == _strip_keys(b, ignored)


# ---------- helpers ----------------------------------------------------

def assert_idempotent(report: IdempotencyReport) -> None:
    """Raise unless ``report.passed()``."""
    if not isinstance(report, IdempotencyReport):
        raise IdempotencyCheckError("assert_idempotent expects IdempotencyReport")
    if report.passed():
        return
    raise IdempotencyCheckError(
        "non-idempotent: " + "; ".join(report.violations)
    )


def generate_idempotency_key(*parts: Any) -> str:
    """Stable SHA-256 hex key from arbitrary parts (e.g. user_id + amount + ts)."""
    serialised = "|".join(repr(p) for p in parts)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()
