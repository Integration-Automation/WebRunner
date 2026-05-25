"""
Test ROI (return-on-investment) scorer.

A pragmatic 0..1 score per test, combining four ingredients:

* **Find rate** — fraction of CI runs in which this test caught a real
  regression (signal).
* **Cost** — average wall-clock duration & flake rate (noise).
* **Coverage** — code paths exclusively covered by this test (unique
  value).
* **Recency** — penalty for tests that haven't run / failed recently.

Use the score to drive ``test_scheduler`` priorities, surface
deletion candidates to ``flakiness_graveyard``, or render dashboards in
``live_dashboard``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, List, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class RoiScorerError(WebRunnerException):
    """Raised on malformed input or inconsistent weights."""


@dataclass
class RoiMetrics:
    """All historical numbers needed to score one test."""

    name: str
    runs: int = 0
    real_failures: int = 0          # confirmed bug catches
    flake_failures: int = 0         # re-runs went green (noise)
    duration_seconds: float = 0     # average wall-clock
    unique_lines_covered: int = 0   # vs. siblings (set-diff)
    days_since_last_run: int = 0
    days_since_last_real_failure: int = 9999

    def __post_init__(self) -> None:
        if not self.name:
            raise RoiScorerError("name must be non-empty")
        if self.runs < 0 or self.duration_seconds < 0:
            raise RoiScorerError("runs/duration must be non-negative")
        if self.real_failures + self.flake_failures > self.runs:
            raise RoiScorerError(
                f"{self.name}: failures > runs (data integrity)"
            )


@dataclass
class Weights:
    find_rate: float = 0.5
    cost: float = 0.2
    coverage: float = 0.2
    recency: float = 0.1

    def total(self) -> float:
        return self.find_rate + self.cost + self.coverage + self.recency


@dataclass
class RoiScore:
    name: str
    score: float
    components: dict
    verdict: str   # "keep" | "review" | "consider-removing"

    def to_dict(self) -> dict:
        return asdict(self)


def _find_rate(m: RoiMetrics) -> float:
    if m.runs == 0:
        return 0.0
    return min(1.0, m.real_failures / m.runs * 10)


def _cost_score(m: RoiMetrics) -> float:
    """Smaller is better — invert and clamp to [0, 1]."""
    if m.runs == 0:
        return 0.5
    flake_rate = m.flake_failures / m.runs
    # 0s + 0 flake → 1.0; 60s & 30 % flake → ~0.0
    duration_penalty = min(1.0, m.duration_seconds / 60)
    flake_penalty = min(1.0, flake_rate / 0.3)
    return max(0.0, 1.0 - 0.5 * duration_penalty - 0.5 * flake_penalty)


def _coverage_score(unique_lines: int) -> float:
    # log-curve: 0 → 0, 50 → 0.5, 200+ → ~1.0
    if unique_lines <= 0:
        return 0.0
    return min(1.0, unique_lines / 200)


def _recency_score(m: RoiMetrics) -> float:
    # half-life: every 30 days the value halves
    if m.days_since_last_real_failure >= 9999:
        return 0.1   # never caught anything — low value but not zero
    return 0.5 ** (m.days_since_last_real_failure / 30)


def score_one(m: RoiMetrics, weights: Weights = Weights()) -> RoiScore:
    if not isinstance(m, RoiMetrics):
        raise RoiScorerError("metrics must be RoiMetrics")
    if abs(weights.total() - 1.0) > 1e-6:
        raise RoiScorerError(
            f"weights must sum to 1.0 (got {weights.total()})"
        )
    find = _find_rate(m)
    cost = _cost_score(m)
    cov = _coverage_score(m.unique_lines_covered)
    rec = _recency_score(m)
    total = (find * weights.find_rate + cost * weights.cost
             + cov * weights.coverage + rec * weights.recency)
    if total >= 0.7:
        verdict = "keep"
    elif total >= 0.4:
        verdict = "review"
    else:
        verdict = "consider-removing"
    return RoiScore(
        name=m.name, score=round(total, 4),
        components={"find_rate": round(find, 4), "cost": round(cost, 4),
                    "coverage": round(cov, 4), "recency": round(rec, 4)},
        verdict=verdict,
    )


def score_many(
    metrics: Sequence[RoiMetrics], weights: Weights = Weights(),
) -> List[RoiScore]:
    if not isinstance(metrics, (list, tuple)):
        raise RoiScorerError("metrics must be a sequence")
    return sorted([score_one(m, weights) for m in metrics],
                  key=lambda s: -s.score)


def removal_candidates(
    scores: Iterable[RoiScore], *, max_score: float = 0.3,
) -> List[RoiScore]:
    if not 0 <= max_score <= 1:
        raise RoiScorerError("max_score must be in [0, 1]")
    return [s for s in scores if s.score <= max_score]
