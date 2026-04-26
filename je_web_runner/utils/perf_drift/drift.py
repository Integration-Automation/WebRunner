"""
Performance baseline drift：看 P95 over N runs 是否在 drift，超 tolerance 就 alert。
Per-metric drift detection. Given a per-metric history of measurements,
compute the baseline P95 over a sliding window, compare it against a
recent window's P95, and flag when the increase exceeds a tolerance.

Designed for FCP / LCP / CLS / TTFB-style metrics where lower is better;
for "higher is better" metrics (frame-rate, throughput) pass
``higher_is_better=True``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PerfDriftError(WebRunnerException):
    """Raised on bad input shape or impossible windowing."""


@dataclass
class _MetricResult:
    metric: str
    baseline_p95: float
    recent_p95: float
    delta: float
    relative_delta: float
    drifted: bool
    direction: str  # "regressed" | "improved" | "stable"


@dataclass
class DriftReport:
    metrics: List[_MetricResult] = field(default_factory=list)

    @property
    def regressions(self) -> List[_MetricResult]:
        return [m for m in self.metrics if m.drifted and m.direction == "regressed"]

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressions)


def percentile(values: Sequence[float], pct: float) -> float:
    """Return the inclusive percentile of ``values``."""
    if not values:
        raise PerfDriftError("values must be non-empty")
    if not 0 <= pct <= 100:
        raise PerfDriftError("pct must be in [0, 100]")
    sorted_values = sorted(values)
    rank = (pct / 100) * (len(sorted_values) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(sorted_values[low])
    weight = rank - low
    return float(sorted_values[low] + (sorted_values[high] - sorted_values[low]) * weight)


def _direction_for(drifted: bool, would_improve: bool) -> str:
    """Bucket a delta into ``regressed`` / ``improved`` / ``stable``."""
    if drifted:
        return "regressed"
    if would_improve:
        return "improved"
    return "stable"


def compute_drift(
    samples: Sequence[float],
    *,
    baseline_window: int,
    recent_window: int,
    tolerance: float = 0.1,
    higher_is_better: bool = False,
    pct: float = 95.0,
    metric: str = "metric",
) -> _MetricResult:
    """
    Compare recent P95 to a baseline P95.

    The baseline window covers the runs immediately preceding the recent
    window: ``samples = […baseline_window…, …recent_window…]``.
    """
    if not isinstance(samples, (list, tuple)):
        raise PerfDriftError("samples must be a list / tuple")
    if baseline_window <= 0 or recent_window <= 0:
        raise PerfDriftError("windows must be > 0")
    if len(samples) < baseline_window + recent_window:
        raise PerfDriftError(
            f"need at least {baseline_window + recent_window} samples for "
            f"metric {metric!r}, got {len(samples)}"
        )
    baseline = samples[-(baseline_window + recent_window):-recent_window]
    recent = samples[-recent_window:]
    base_p = percentile(baseline, pct)
    new_p = percentile(recent, pct)
    delta = new_p - base_p
    relative = delta / base_p if base_p else 0.0
    if higher_is_better:
        drifted = relative <= -tolerance
        direction = _direction_for(drifted, relative >= tolerance)
    else:
        drifted = relative >= tolerance
        direction = _direction_for(drifted, relative <= -tolerance)
    return _MetricResult(
        metric=metric,
        baseline_p95=base_p,
        recent_p95=new_p,
        delta=delta,
        relative_delta=relative,
        drifted=drifted,
        direction=direction,
    )


def detect_drift(
    metrics: Dict[str, Sequence[float]],
    *,
    baseline_window: int = 20,
    recent_window: int = 5,
    tolerance: float = 0.1,
    higher_is_better: Optional[Iterable[str]] = None,
    pct: float = 95.0,
) -> DriftReport:
    """
    Run :func:`compute_drift` for every metric in ``metrics`` and aggregate.
    """
    if not isinstance(metrics, dict) or not metrics:
        raise PerfDriftError("metrics must be a non-empty dict")
    higher_is_better_set = set(higher_is_better or [])
    report = DriftReport()
    for metric_name, samples in metrics.items():
        result = compute_drift(
            samples,
            baseline_window=baseline_window,
            recent_window=recent_window,
            tolerance=tolerance,
            higher_is_better=metric_name in higher_is_better_set,
            pct=pct,
            metric=str(metric_name),
        )
        report.metrics.append(result)
    return report


def assert_no_regression(report: DriftReport,
                         allow_metrics: Optional[Iterable[str]] = None) -> None:
    """Raise if any drifted+regressed metric remains."""
    allow = set(allow_metrics or [])
    bad = [m for m in report.regressions if m.metric not in allow]
    if bad:
        sample = [
            {
                "metric": m.metric,
                "baseline_p95": m.baseline_p95,
                "recent_p95": m.recent_p95,
                "relative_delta": round(m.relative_delta, 4),
            }
            for m in bad[:5]
        ]
        raise PerfDriftError(f"{len(bad)} perf regression(s): {sample}")
