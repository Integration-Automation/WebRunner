"""
每個 suite 的雲端費用 / 分鐘數 / CO₂ 估算。
跑了多久(從 ledger 拿時間) × 在哪種 runner(本地 / SauceLabs / BrowserStack /
LambdaTest)× 平台每分鐘費率 = 美金。再乘以平均碳排係數 = 估算 CO₂。

These numbers are estimates by design — actual cloud bills include
session-start overhead, video upload, parallel-slot pricing, regional
multipliers. The point isn't accounting precision; it's "this suite costs
$2 / day, that suite costs $200 / day" so you know where to spend
engineering effort on optimisation.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class TestCostEstimatorError(WebRunnerException):
    """Raised on bad ledger / rate-card / inputs."""

    __test__ = False  # domain exception, not a pytest test class


# ---------- model -------------------------------------------------------

@dataclass(frozen=True)
class RateCard:
    """Per-runner cost knobs."""

    runner: str
    usd_per_minute: float
    grams_co2_per_minute: float = 0.0  # rough datacenter intensity
    minimum_minutes: float = 0.0       # billed minimum per session

    def __post_init__(self) -> None:
        if self.usd_per_minute < 0:
            raise TestCostEstimatorError("usd_per_minute must be >= 0")
        if self.grams_co2_per_minute < 0:
            raise TestCostEstimatorError("grams_co2_per_minute must be >= 0")
        if self.minimum_minutes < 0:
            raise TestCostEstimatorError("minimum_minutes must be >= 0")


# Sensible defaults; teams should override with their own contract rates.
DEFAULT_RATE_CARDS: Sequence[RateCard] = (
    RateCard(runner="local", usd_per_minute=0.0, grams_co2_per_minute=2.0),
    RateCard(runner="saucelabs", usd_per_minute=0.18, grams_co2_per_minute=10.0,
             minimum_minutes=1.0),
    RateCard(runner="browserstack", usd_per_minute=0.16, grams_co2_per_minute=10.0,
             minimum_minutes=1.0),
    RateCard(runner="lambdatest", usd_per_minute=0.15, grams_co2_per_minute=10.0,
             minimum_minutes=1.0),
    RateCard(runner="github_actions_linux", usd_per_minute=0.008,
             grams_co2_per_minute=4.0),
    RateCard(runner="github_actions_macos", usd_per_minute=0.08,
             grams_co2_per_minute=8.0),
)


def rate_card_index(cards: Sequence[RateCard]) -> Dict[str, RateCard]:
    """Build a lookup keyed by runner name; rejects duplicates."""
    out: Dict[str, RateCard] = {}
    for card in cards:
        if card.runner in out:
            raise TestCostEstimatorError(f"duplicate runner {card.runner!r}")
        out[card.runner] = card
    return out


# ---------- ledger input -----------------------------------------------

@dataclass
class RunRow:
    """One ledger row reduced to what cost cares about."""

    test_id: str
    runner: str
    duration_seconds: float

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise TestCostEstimatorError(
                f"duration_seconds must be >= 0 for {self.test_id}"
            )


def load_runs(path: Union[str, Path]) -> List[RunRow]:  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    """Parse a ledger JSON file. Rows missing duration are skipped."""
    p = Path(path)
    if not p.exists():
        raise TestCostEstimatorError(f"ledger not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as error:
        raise TestCostEstimatorError(f"ledger not JSON: {error}") from error
    if not isinstance(data, dict) or "runs" not in data:
        raise TestCostEstimatorError("ledger missing 'runs' key")
    out: List[RunRow] = []
    for raw in data["runs"]:
        if not isinstance(raw, dict):
            continue
        duration = raw.get("duration_seconds")
        if duration is None:
            continue
        test_id = raw.get("test_id") or raw.get("path")
        runner = raw.get("runner") or "local"
        if not isinstance(test_id, str) or not isinstance(runner, str):
            continue
        try:
            out.append(RunRow(
                test_id=test_id,
                runner=runner,
                duration_seconds=float(duration),
            ))
        except TestCostEstimatorError:
            raise
        except (TypeError, ValueError):
            continue
    return out


# ---------- estimate ----------------------------------------------------

@dataclass
class CostBreakdown:
    """Per-runner roll-up of the estimate."""

    runner: str
    runs: int
    billed_minutes: float
    usd: float
    grams_co2: float


@dataclass
class CostEstimate:
    """Aggregate estimate returned by :func:`estimate_runs`."""

    total_runs: int
    total_billed_minutes: float
    total_usd: float
    total_grams_co2: float
    by_runner: Dict[str, CostBreakdown] = field(default_factory=dict)
    by_test: Dict[str, float] = field(default_factory=dict)
    unknown_runners: List[str] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_runs": self.total_runs,
            "total_billed_minutes": round(self.total_billed_minutes, 4),
            "total_usd": round(self.total_usd, 4),
            "total_grams_co2": round(self.total_grams_co2, 4),
            "by_runner": {k: asdict(v) for k, v in self.by_runner.items()},
            "by_test": {k: round(v, 4) for k, v in self.by_test.items()},
            "unknown_runners": sorted(self.unknown_runners),
            "generated_at": self.generated_at,
        }


def _billed_minutes(seconds: float, card: RateCard) -> float:
    minutes = seconds / 60.0
    return max(minutes, card.minimum_minutes)


def estimate_runs(
    runs: Sequence[RunRow],
    *,
    rate_cards: Sequence[RateCard] = DEFAULT_RATE_CARDS,
) -> CostEstimate:
    """Combine run history × rate card → :class:`CostEstimate`."""
    if not runs:
        raise TestCostEstimatorError("runs must be non-empty")
    index = rate_card_index(rate_cards)
    estimate = CostEstimate(
        total_runs=0,
        total_billed_minutes=0.0,
        total_usd=0.0,
        total_grams_co2=0.0,
        generated_at=datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
    )
    unknown: set = set()
    for run in runs:
        card = index.get(run.runner)
        if card is None:
            unknown.add(run.runner)
            continue
        minutes = _billed_minutes(run.duration_seconds, card)
        usd = round(minutes * card.usd_per_minute, 6)
        co2 = round(minutes * card.grams_co2_per_minute, 6)
        estimate.total_runs += 1
        estimate.total_billed_minutes += minutes
        estimate.total_usd += usd
        estimate.total_grams_co2 += co2
        bucket = estimate.by_runner.get(run.runner) or CostBreakdown(
            runner=run.runner, runs=0, billed_minutes=0.0, usd=0.0, grams_co2=0.0,
        )
        bucket.runs += 1
        bucket.billed_minutes = round(bucket.billed_minutes + minutes, 6)
        bucket.usd = round(bucket.usd + usd, 6)
        bucket.grams_co2 = round(bucket.grams_co2 + co2, 6)
        estimate.by_runner[run.runner] = bucket
        estimate.by_test[run.test_id] = round(
            estimate.by_test.get(run.test_id, 0.0) + usd, 6,
        )
    estimate.unknown_runners = sorted(unknown)
    return estimate


# ---------- reporting --------------------------------------------------

def estimate_markdown(estimate: CostEstimate, *, top_tests: int = 5) -> str:
    """Render a small markdown report (PR comment / Slack-ready)."""
    if not isinstance(estimate, CostEstimate):
        raise TestCostEstimatorError("estimate_markdown expects CostEstimate")
    if top_tests < 0:
        raise TestCostEstimatorError("top_tests must be >= 0")
    lines = [
        "### Test cost estimate",
        "",
        f"- Total runs: **{estimate.total_runs}**",
        f"- Billed minutes: **{estimate.total_billed_minutes:.1f}**",
        f"- Estimated USD: **${estimate.total_usd:.2f}**",
        f"- Estimated CO₂: **{estimate.total_grams_co2 / 1000:.2f} kg**",
    ]
    if estimate.by_runner:
        lines.append("")
        lines.append("| Runner | Runs | Min | USD | CO₂ g |")
        lines.append("|--------|------|-----|-----|-------|")
        for name, bucket in sorted(estimate.by_runner.items()):
            lines.append(
                f"| {name} | {bucket.runs} | {bucket.billed_minutes:.1f} | "
                f"${bucket.usd:.2f} | {bucket.grams_co2:.1f} |"
            )
    if estimate.by_test and top_tests:
        biggest = sorted(estimate.by_test.items(), key=lambda kv: -kv[1])[:top_tests]
        lines.append("")
        lines.append(f"**Top {len(biggest)} costliest tests:**")
        for test_id, usd in biggest:
            lines.append(f"- `{test_id}`: ${usd:.2f}")
    if estimate.unknown_runners:
        lines.append("")
        lines.append(
            "_Runners without rate cards skipped: "
            + ", ".join(estimate.unknown_runners) + "._"
        )
    return "\n".join(lines) + "\n"
