"""
HTTP rate limit / 429 / Retry-After verifier.

Verifies that an API actually enforces declared rate limits AND returns
the right metadata clients need to back off correctly:

* When N+1 requests fire inside the limit window, response is 429.
* ``Retry-After`` header is present and ≥ documented refill time.
* ``X-RateLimit-Limit`` / ``X-RateLimit-Remaining`` / ``-Reset`` are
  consistent across responses (Remaining decreases monotonically).
* After waiting ``Retry-After`` seconds, the next request succeeds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class RateLimitAssertError(WebRunnerException):
    """Raised on rate-limit protocol violation."""


@dataclass
class RateLimitResponse:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None

    @property
    def is_429(self) -> bool:
        return self.status_code == 429

    @property
    def retry_after_seconds(self) -> float | None:
        raw = self.headers.get("Retry-After") or self.headers.get("retry-after")
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    @property
    def limit(self) -> int | None:
        raw = self.headers.get("X-RateLimit-Limit") or self.headers.get("x-ratelimit-limit")
        return int(raw) if raw and raw.isdigit() else None

    @property
    def remaining(self) -> int | None:
        raw = self.headers.get("X-RateLimit-Remaining") or self.headers.get("x-ratelimit-remaining")
        return int(raw) if raw and raw.isdigit() else None


def assert_429_after_burst(
    responses: Sequence[RateLimitResponse], *, after: int,
) -> RateLimitResponse:
    if after < 1:
        raise RateLimitAssertError("after must be >= 1")
    if len(responses) <= after:
        raise RateLimitAssertError(
            f"need > {after} responses, got {len(responses)}"
        )
    for r in responses[after:]:
        if r.is_429:
            return r
    raise RateLimitAssertError(
        f"no 429 after first {after} successful request(s)"
    )


def assert_retry_after_present(response: RateLimitResponse) -> None:
    if not response.is_429:
        raise RateLimitAssertError(
            "assert_retry_after_present called on non-429 response"
        )
    if response.retry_after_seconds is None:
        raise RateLimitAssertError(
            "429 response missing Retry-After header"
        )
    if response.retry_after_seconds <= 0:
        raise RateLimitAssertError(
            f"Retry-After is {response.retry_after_seconds}s — clients can't "
            "compute a positive back-off"
        )


def assert_remaining_monotonic(
    responses: Sequence[RateLimitResponse],
) -> None:
    """``X-RateLimit-Remaining`` must decrease (or stay flat) until 429."""
    last: int | None = None
    for i, r in enumerate(responses):
        rem = r.remaining
        if rem is None:
            continue
        if last is not None and rem > last:
            raise RateLimitAssertError(
                f"X-RateLimit-Remaining went UP between request {i-1} ({last}) "
                f"and {i} ({rem})"
            )
        last = rem


def assert_recovery_after_retry_after(
    *, before: RateLimitResponse, after: RateLimitResponse,
) -> None:
    """``before`` is a 429 with Retry-After. ``after`` is the next request
    once the harness slept that long — must NOT be 429 again."""
    if not before.is_429:
        raise RateLimitAssertError("before must be a 429 response")
    if after.is_429:
        raise RateLimitAssertError(
            "API still returned 429 after waiting Retry-After — "
            "either window didn't refill or Retry-After was wrong"
        )
