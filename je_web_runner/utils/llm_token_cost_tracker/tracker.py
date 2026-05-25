"""
Per-test LLM token & dollar cost tracker.

Tests of AI features burn real money. This module gives the test harness
a tiny ledger to:

* Record each model call with input/output token counts.
* Look up the per-1K-token price from a built-in rate card (Claude /
  GPT / Gemini families) with an override hook for self-hosted models.
* Roll up totals per test, per file, or per run.
* Enforce a budget assertion (``assert_under_budget``).

Rate card numbers are conservative defaults; pass ``rate_card_override``
in production to keep them current.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class LlmTokenCostError(WebRunnerException):
    """Raised on malformed input or budget violation."""


# USD per 1K tokens (input, output). Conservative late-2025 numbers.
DEFAULT_RATE_CARD: Dict[str, Dict[str, float]] = {
    "claude-opus-4-7":    {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-6":  {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5":   {"input": 0.001, "output": 0.005},
    "gpt-4o":             {"input": 0.005, "output": 0.015},
    "gpt-4o-mini":        {"input": 0.000150, "output": 0.000600},
    "gemini-2.5-pro":     {"input": 0.00125, "output": 0.005},
    "gemini-2.5-flash":   {"input": 0.000075, "output": 0.0003},
}


@dataclass
class CallRecord:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    test_name: str = ""

    def __post_init__(self) -> None:
        if not self.model:
            raise LlmTokenCostError("model name required")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise LlmTokenCostError("token counts must be non-negative")


@dataclass
class Tally:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _resolve_price(
    model: str, rate_card: Mapping[str, Mapping[str, float]],
) -> Mapping[str, float]:
    if model in rate_card:
        return rate_card[model]
    # fallback: prefix-match (e.g. claude-opus-4-7-2026-05-01)
    for prefix, prices in rate_card.items():
        if model.startswith(prefix):
            return prices
    raise LlmTokenCostError(
        f"no rate-card entry for model {model!r}; "
        "pass rate_card_override to add it"
    )


def compute_cost(
    record: CallRecord, *,
    rate_card_override: Optional[Mapping[str, Mapping[str, float]]] = None,
) -> float:
    rates = dict(DEFAULT_RATE_CARD)
    if rate_card_override:
        rates.update(rate_card_override)
    prices = _resolve_price(record.model, rates)
    return ((record.input_tokens / 1000) * float(prices.get("input", 0))
            + (record.output_tokens / 1000) * float(prices.get("output", 0)))


def tally(
    records: Iterable[CallRecord], *,
    rate_card_override: Optional[Mapping[str, Mapping[str, float]]] = None,
) -> Tally:
    out = Tally()
    for r in records:
        if not isinstance(r, CallRecord):
            raise LlmTokenCostError("records must be CallRecord instances")
        out.input_tokens += r.input_tokens
        out.output_tokens += r.output_tokens
        out.cost_usd += compute_cost(r, rate_card_override=rate_card_override)
        out.calls += 1
    out.cost_usd = round(out.cost_usd, 6)
    return out


def tally_by_test(
    records: Iterable[CallRecord],
    *, rate_card_override: Optional[Mapping[str, Mapping[str, float]]] = None,
) -> Dict[str, Tally]:
    buckets: Dict[str, List[CallRecord]] = defaultdict(list)
    for r in records:
        buckets[r.test_name or "(unknown)"].append(r)
    return {k: tally(v, rate_card_override=rate_card_override)
            for k, v in buckets.items()}


def assert_under_budget(
    summary: Tally, *, max_usd: float,
) -> None:
    if max_usd <= 0:
        raise LlmTokenCostError("max_usd must be positive")
    if summary.cost_usd > max_usd:
        raise LlmTokenCostError(
            f"LLM cost ${summary.cost_usd:.4f} exceeds budget ${max_usd:.4f}"
        )


def top_spenders(
    by_test: Mapping[str, Tally], *, top_n: int = 5,
) -> List[Dict[str, Any]]:
    if top_n < 1:
        raise LlmTokenCostError("top_n must be >= 1")
    items = sorted(by_test.items(), key=lambda kv: -kv[1].cost_usd)
    return [{"test": k, **v.to_dict()} for k, v in items[:top_n]]
