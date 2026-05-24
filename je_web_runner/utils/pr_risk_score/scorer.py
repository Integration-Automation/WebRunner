"""
融合 flake / impact / locator_health / coverage 訊號,給 PR 一個 0-100 風險分數。
The pieces this depends on (``flake_detector``, ``impact_analysis``,
``locator_health``, ``coverage_map``) already exist; this module just
combines their per-PR rollups into a single decision-friendly number plus
a human-readable reason list.

Risk model: weighted sum, each signal clipped to ``[0, 1]``. Default
weights are tuned to roughly match what humans flag as "scary PR" in our
own retrospective sampling, but they're parameterised so teams can tune
them per repo without forking.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PrRiskScoreError(WebRunnerException):
    """Raised on invalid inputs or weight totals that won't normalise."""


# ---------- inputs ------------------------------------------------------

@dataclass
class PrSignals:
    """
    Per-PR aggregate signals. Each field is optional so a partial signal
    set still produces a (less-confident) score.
    """

    # Test stability
    flaky_tests_touched: int = 0
    total_tests_touched: int = 0
    avg_flake_score: float = 0.0

    # Blast radius
    impacted_modules: int = 0
    repo_modules: int = 0
    impacted_critical_paths: int = 0

    # Locator hygiene
    fragile_locators_touched: int = 0
    total_locators_touched: int = 0

    # Coverage
    lines_added: int = 0
    lines_covered: int = 0

    # Other contextual signals
    migration_files_changed: int = 0
    security_files_changed: int = 0

    def __post_init__(self) -> None:
        for name in (
            "flaky_tests_touched", "total_tests_touched",
            "impacted_modules", "repo_modules", "impacted_critical_paths",
            "fragile_locators_touched", "total_locators_touched",
            "lines_added", "lines_covered",
            "migration_files_changed", "security_files_changed",
        ):
            if getattr(self, name) < 0:
                raise PrRiskScoreError(f"{name} must be >= 0")
        if not 0.0 <= self.avg_flake_score <= 1.0:
            raise PrRiskScoreError("avg_flake_score must be in [0, 1]")


@dataclass(frozen=True)
class RiskWeights:
    """Per-signal contribution. Should be non-negative; need not sum to 1."""

    flake: float = 2.0
    blast_radius: float = 2.0
    critical_path: float = 1.5
    locator_fragility: float = 1.0
    coverage_gap: float = 1.5
    migration: float = 1.0
    security: float = 1.0

    def total(self) -> float:
        return sum(asdict(self).values())


@dataclass
class RiskReport:
    """Result of :func:`score_pr`."""

    score: float  # 0..100
    level: str   # "low" | "medium" | "high" | "critical"
    reasons: List[str] = field(default_factory=list)
    contributions: Dict[str, float] = field(default_factory=dict)

    def is_blocking(self, block_at: float = 75.0) -> bool:
        return self.score >= block_at


# ---------- scoring -----------------------------------------------------

def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, numerator / denominator))


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


_SIGNAL_NAMES = (
    "flake", "blast_radius", "critical_path",
    "locator_fragility", "coverage_gap", "migration", "security",
)


def _signal_components(signals: PrSignals) -> Dict[str, float]:
    flake_touched_ratio = _ratio(
        signals.flaky_tests_touched, signals.total_tests_touched,
    )
    flake = _clip(0.7 * flake_touched_ratio + 0.3 * signals.avg_flake_score)
    blast = _ratio(signals.impacted_modules, signals.repo_modules)
    # Critical path: each impacted critical path adds 0.25, capped at 1.0
    critical = _clip(0.25 * signals.impacted_critical_paths)
    locator = _ratio(signals.fragile_locators_touched, signals.total_locators_touched)
    if signals.lines_added <= 0:
        coverage_gap = 0.0
    else:
        coverage_gap = _clip(1.0 - _ratio(signals.lines_covered, signals.lines_added))
    migration = _clip(0.5 * signals.migration_files_changed)
    security = _clip(0.5 * signals.security_files_changed)
    return {
        "flake": flake,
        "blast_radius": blast,
        "critical_path": critical,
        "locator_fragility": locator,
        "coverage_gap": coverage_gap,
        "migration": migration,
        "security": security,
    }


def _format_reason(name: str, component: float, weight: float) -> Optional[str]:
    if component <= 0:
        return None
    pct = round(component * 100)
    return f"{name.replace('_', ' ')}: {pct}% signal × weight {weight:.1f}"


def _level_for(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def score_pr(
    signals: PrSignals,
    weights: Optional[RiskWeights] = None,
) -> RiskReport:
    """Combine ``signals`` × ``weights`` into a 0–100 :class:`RiskReport`."""
    if not isinstance(signals, PrSignals):
        raise PrRiskScoreError("signals must be a PrSignals instance")
    weights = weights or RiskWeights()
    weight_total = weights.total()
    if weight_total <= 0:
        raise PrRiskScoreError("at least one weight must be > 0")
    components = _signal_components(signals)
    contributions: Dict[str, float] = {}
    weighted_sum = 0.0
    for name in _SIGNAL_NAMES:
        weight = getattr(weights, name)
        component = components[name]
        contrib = component * weight
        weighted_sum += contrib
        contributions[name] = round(contrib, 4)
    normalised = weighted_sum / weight_total
    score = round(_clip(normalised) * 100.0, 2)
    reasons = sorted(
        (
            r for r in (
                _format_reason(name, components[name], getattr(weights, name))
                for name in _SIGNAL_NAMES
            ) if r is not None
        ),
        key=lambda s: -float(s.split("%")[0].rsplit(":", 1)[-1].strip()),
    )
    return RiskReport(
        score=score,
        level=_level_for(score),
        reasons=reasons,
        contributions=contributions,
    )


# ---------- formatting --------------------------------------------------

def report_markdown(report: RiskReport) -> str:
    """Render a :class:`RiskReport` as a small markdown block for PR comments."""
    lines = [
        f"### PR risk: **{report.score:.1f} / 100** ({report.level})",
        "",
    ]
    if report.reasons:
        lines.append("Top contributing signals:")
        lines.extend(f"- {reason}" for reason in report.reasons)
    else:
        lines.append("_No risk signals tripped._")
    return "\n".join(lines) + "\n"


def aggregate_signals(per_file: Sequence[Dict[str, Any]]) -> PrSignals:
    """
    Reduce a per-file signal list (from upstream tools) into one
    :class:`PrSignals`. Unknown keys are ignored so callers can pass
    richer dicts without breaking.
    """
    totals: Dict[str, int] = {
        name: 0 for name in (
            "flaky_tests_touched", "total_tests_touched",
            "impacted_modules", "impacted_critical_paths",
            "fragile_locators_touched", "total_locators_touched",
            "lines_added", "lines_covered",
            "migration_files_changed", "security_files_changed",
        )
    }
    flake_scores: List[float] = []
    repo_modules = 0
    for entry in per_file:
        if not isinstance(entry, dict):
            continue
        for key in totals:
            value = entry.get(key)
            if isinstance(value, int) and value >= 0:
                totals[key] += value
        score = entry.get("avg_flake_score")
        if isinstance(score, (int, float)) and 0 <= score <= 1:
            flake_scores.append(float(score))
        rm = entry.get("repo_modules")
        if isinstance(rm, int) and rm > repo_modules:
            repo_modules = rm
    avg_flake = sum(flake_scores) / len(flake_scores) if flake_scores else 0.0
    return PrSignals(
        avg_flake_score=round(avg_flake, 4),
        repo_modules=repo_modules,
        **totals,
    )
