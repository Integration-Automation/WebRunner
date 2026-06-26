"""
Lighthouse score regression tracker.

Reads a Lighthouse JSON result (run via ``lighthouse --output=json``)
and:

* Extracts the four category scores (performance / accessibility /
  best-practices / SEO) plus PWA when present.
* Compares against a baseline JSON of the same shape.
* Reports any per-category drop > ``threshold`` (default 5 points).
* Provides a metric-level diff for the Core Web Vitals (LCP / CLS / TBT)
  with milliseconds-resolved deltas.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from je_web_runner.utils.exception.exceptions import WebRunnerException


class LighthouseRegressionError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


_CATEGORY_KEYS = ("performance", "accessibility",
                  "best-practices", "seo", "pwa")
_METRIC_KEYS = ("largest-contentful-paint", "cumulative-layout-shift",
                "total-blocking-time", "first-contentful-paint",
                "speed-index")


@dataclass
class LighthouseSnapshot:
    scores: dict[str, float] = field(default_factory=dict)        # 0..100
    metrics: dict[str, float] = field(default_factory=dict)       # numeric

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _coerce_score(key: str, raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return round(float(raw) * 100, 1)
    except (TypeError, ValueError) as exc:
        raise LighthouseRegressionError(
            f"category {key!r} score is non-numeric: {raw!r}"
        ) from exc


def _coerce_metric(key: str, raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise LighthouseRegressionError(
            f"metric {key!r} numericValue is non-numeric"
        ) from exc


def _collect_scores(categories: Mapping[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for key in _CATEGORY_KEYS:
        entry = categories.get(key)
        if isinstance(entry, Mapping) and "score" in entry:
            value = _coerce_score(key, entry["score"])
            if value is not None:
                scores[key] = value
    return scores


def _collect_metrics(audits: Mapping[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for key in _METRIC_KEYS:
        entry = audits.get(key)
        if isinstance(entry, Mapping):
            value = _coerce_metric(key, entry.get("numericValue"))
            if value is not None:
                metrics[key] = value
    return metrics


def parse_report(report: Any) -> LighthouseSnapshot:
    if not isinstance(report, Mapping):
        raise LighthouseRegressionError("report must be a mapping")
    categories = report.get("categories") or {}
    if not isinstance(categories, Mapping):
        raise LighthouseRegressionError("report.categories must be a mapping")
    audits = report.get("audits") or {}
    return LighthouseSnapshot(
        scores=_collect_scores(categories),
        metrics=_collect_metrics(audits if isinstance(audits, Mapping) else {}),
    )


@dataclass
class ScoreDelta:
    category: str
    baseline: float
    head: float

    @property
    def delta(self) -> float:
        return self.head - self.baseline


@dataclass
class RegressionReport:
    score_changes: list[ScoreDelta] = field(default_factory=list)
    metric_changes: list[ScoreDelta] = field(default_factory=list)


def diff(baseline: LighthouseSnapshot, head: LighthouseSnapshot) -> RegressionReport:
    report = RegressionReport()
    for key in _CATEGORY_KEYS:
        if key not in baseline.scores and key not in head.scores:
            continue
        b = baseline.scores.get(key, head.scores.get(key, 0))
        h = head.scores.get(key, baseline.scores.get(key, 0))
        if b != h:
            report.score_changes.append(
                ScoreDelta(category=key, baseline=b, head=h),
            )
    for key in _METRIC_KEYS:
        if key not in baseline.metrics and key not in head.metrics:
            continue
        b = baseline.metrics.get(key, head.metrics.get(key, 0))
        h = head.metrics.get(key, baseline.metrics.get(key, 0))
        if b != h:
            report.metric_changes.append(
                ScoreDelta(category=key, baseline=b, head=h),
            )
    return report


def assert_no_score_regression(
    report: RegressionReport, *, threshold_points: float = 5,
) -> None:
    if threshold_points <= 0:
        raise LighthouseRegressionError("threshold_points must be positive")
    drops = [c for c in report.score_changes
             if c.delta < -threshold_points]
    if drops:
        details = [f"{c.category}: {c.baseline}→{c.head}" for c in drops]
        raise LighthouseRegressionError(
            f"Lighthouse score regressed by > {threshold_points}: {details}"
        )


def assert_metric_within(
    snap: LighthouseSnapshot, *, metric: str, max_value: float,
) -> None:
    if metric not in _METRIC_KEYS:
        raise LighthouseRegressionError(
            f"unknown metric {metric!r}; choose from {_METRIC_KEYS}"
        )
    value = snap.metrics.get(metric)
    if value is None:
        raise LighthouseRegressionError(f"metric {metric!r} missing in snapshot")
    if value > max_value:
        raise LighthouseRegressionError(
            f"metric {metric} = {value:.0f} exceeds budget {max_value:.0f}"
        )
