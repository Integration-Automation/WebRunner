"""
依 classifier 結果調整重試策略：transient/flaky 多試幾次，real 直接放棄。
Adaptive retry policy. Wraps a callable, classifies any raised exception via
the ledger-aware classifier, and retries only when the failure is transient
or flaky. Real bugs short-circuit so the run fails fast.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.run_ledger.classifier import classify


class AdaptiveRetryError(WebRunnerException):
    """Raised when a non-retryable failure is classified as ``real``."""


@dataclass
class RetryDecision:
    """Outcome of a single retry attempt."""

    attempt: int
    category: str
    sleep_seconds: float
    will_retry: bool
    error_repr: str


@dataclass
class RetryPolicy:
    """Per-category retry budget; flat backoff per attempt."""

    transient_max: int = 3
    flaky_max: int = 2
    environment_max: int = 1
    real_max: int = 0
    base_backoff: float = 0.25
    max_backoff: float = 4.0
    history: List[RetryDecision] = field(default_factory=list)

    def budget_for(self, category: str) -> int:
        return {
            "transient": self.transient_max,
            "flaky": self.flaky_max,
            "environment": self.environment_max,
            "real": self.real_max,
        }.get(category, 0)

    def backoff_for(self, attempt: int) -> float:
        delay = self.base_backoff * (2 ** max(0, attempt - 1))
        return min(self.max_backoff, delay)


def run_with_retry(
    func: Callable[..., Any],
    *args: Any,
    policy: Optional[RetryPolicy] = None,
    ledger_path: Optional[str] = None,
    file_path: Optional[str] = None,
    sleep: Callable[[float], None] = time.sleep,
    **kwargs: Any,
) -> Any:
    """
    執行 ``func``，依分類器結果決定是否重試
    Call ``func(*args, **kwargs)`` and retry only when the classifier labels
    the exception as ``transient`` / ``flaky`` / ``environment``. ``real``
    failures raise :class:`AdaptiveRetryError` immediately.
    """
    used_policy = policy or RetryPolicy()
    attempt = 0
    while True:
        attempt += 1
        try:
            return func(*args, **kwargs)
        except Exception as error:  # pylint: disable=broad-except
            decision = _record_attempt(used_policy, attempt, error, ledger_path, file_path)
            if not decision.will_retry:
                if decision.category == "real":
                    raise AdaptiveRetryError(
                        f"non-retryable real failure: {decision.error_repr[:200]}"
                    ) from error
                raise
            if decision.sleep_seconds > 0:
                sleep(decision.sleep_seconds)


def _record_attempt(
    policy: RetryPolicy,
    attempt: int,
    error: BaseException,
    ledger_path: Optional[str],
    file_path: Optional[str],
) -> RetryDecision:
    error_repr = repr(error)
    category = classify(error_repr, ledger_path=ledger_path, file_path=file_path)
    will_retry = attempt <= policy.budget_for(category)
    decision = RetryDecision(
        attempt=attempt,
        category=category,
        sleep_seconds=policy.backoff_for(attempt) if will_retry else 0.0,
        will_retry=will_retry,
        error_repr=error_repr,
    )
    policy.history.append(decision)
    web_runner_logger.warning(
        f"adaptive_retry attempt={attempt} category={category} "
        f"will_retry={will_retry} err={error_repr[:120]}"
    )
    return decision


def summarise_history(policy: RetryPolicy) -> Dict[str, Any]:
    """Aggregate decision counts for reporting."""
    by_category: Dict[str, int] = {}
    for decision in policy.history:
        by_category[decision.category] = by_category.get(decision.category, 0) + 1
    return {
        "attempts": len(policy.history),
        "by_category": by_category,
        "last_will_retry": policy.history[-1].will_retry if policy.history else None,
    }
