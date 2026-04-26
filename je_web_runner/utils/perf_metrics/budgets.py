"""
依路由設定 FCP/LCP/CLS/TTFB 預算，CI 友善的 JSON schema。
Per-route performance budgets. Routes are matched in declaration order
(first hit wins) and each metric has an inclusive upper bound; metrics
without a configured budget are ignored.

The budget JSON schema is intentionally simple so it can live next to the
action JSON in the same repo:

.. code-block:: json

    [
      {"path": "/checkout", "metrics": {"lcp_ms": 2500, "cls": 0.1}},
      {"path_glob": "/products/*", "metrics": {"fcp_ms": 1800}}
    ]
"""
from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PerfBudgetError(WebRunnerException):
    """Raised when budget config is invalid or assertions fail."""


@dataclass
class RouteBudget:
    """Single budget entry."""

    path: Optional[str] = None
    path_glob: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)

    def matches(self, route_path: str) -> bool:
        if self.path is not None and self.path == route_path:
            return True
        if self.path_glob is not None and fnmatch.fnmatchcase(route_path, self.path_glob):
            return True
        return False


def load_budgets(source: Union[str, Path, list]) -> List[RouteBudget]:
    """Load budgets from a path, JSON string, or in-memory list."""
    if isinstance(source, list):
        raw = source
    elif isinstance(source, (str, Path)):
        path = Path(source)
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except ValueError as error:
                raise PerfBudgetError(f"budget file is not JSON: {error}") from error
        else:
            try:
                raw = json.loads(str(source))
            except ValueError as error:
                raise PerfBudgetError(f"budget string is not JSON: {error}") from error
    else:
        raise PerfBudgetError(f"unsupported source type: {type(source).__name__}")
    if not isinstance(raw, list):
        raise PerfBudgetError("budget root must be a list")
    budgets: List[RouteBudget] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise PerfBudgetError(f"budget[{index}] must be an object")
        if "path" not in entry and "path_glob" not in entry:
            raise PerfBudgetError(f"budget[{index}]: needs 'path' or 'path_glob'")
        metrics = entry.get("metrics") or {}
        if not isinstance(metrics, dict) or not metrics:
            raise PerfBudgetError(f"budget[{index}]: 'metrics' must be a non-empty object")
        budgets.append(RouteBudget(
            path=entry.get("path"),
            path_glob=entry.get("path_glob"),
            metrics={k: float(v) for k, v in metrics.items()},
        ))
    return budgets


@dataclass
class BudgetCheckResult:
    route: str
    matched_rule: Optional[RouteBudget]
    breaches: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.breaches


def evaluate_metrics(
    route_path: str,
    metrics: Dict[str, float],
    budgets: Sequence[RouteBudget],
) -> BudgetCheckResult:
    """Find the first matching rule and check every configured metric."""
    rule = next((b for b in budgets if b.matches(route_path)), None)
    result = BudgetCheckResult(route=route_path, matched_rule=rule)
    if rule is None:
        return result
    for metric_name, max_allowed in rule.metrics.items():
        value = metrics.get(metric_name)
        if value is None:
            result.breaches.append({
                "metric": metric_name,
                "expected_max": max_allowed,
                "value": None,
                "reason": "metric missing",
            })
            continue
        if value > max_allowed:
            result.breaches.append({
                "metric": metric_name,
                "expected_max": max_allowed,
                "value": value,
            })
    return result


def assert_within_budget(result: BudgetCheckResult) -> None:
    if result.matched_rule is None:
        return  # no rule for this route — caller decides whether that's OK
    if not result.passed:
        raise PerfBudgetError(
            f"perf budget breach for {result.route!r}: {result.breaches[:3]}"
        )
