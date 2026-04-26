"""Façade: a11y diff / a11y trend / perf budgets / perf drift / trend / cluster."""
from je_web_runner.utils.a11y_trend.trend import (
    A11yTrendError,
    A11yTrendPoint,
    aggregate_history,
    render_html as render_a11y_trend_html,
)
from je_web_runner.utils.accessibility.a11y_diff import (
    A11yDiff,
    A11yDiffError,
    assert_no_regressions,
    diff_violations,
)
from je_web_runner.utils.failure_cluster.clustering import (
    FailureCluster,
    FailureClusterError,
    cluster_failures,
    normalise_error,
)
from je_web_runner.utils.perf_drift.drift import (
    DriftReport,
    PerfDriftError,
    compute_drift,
    detect_drift,
    percentile,
)
from je_web_runner.utils.perf_metrics.budgets import (
    BudgetCheckResult,
    PerfBudgetError,
    RouteBudget,
    assert_within_budget,
    evaluate_metrics,
    load_budgets,
)
from je_web_runner.utils.trend_dashboard.trend import (
    TrendDashboardError,
    compute_trend,
    render_html as render_run_trend_html,
)

__all__ = [
    "A11yDiff", "A11yDiffError", "A11yTrendError", "A11yTrendPoint",
    "aggregate_history", "assert_no_regressions", "diff_violations",
    "render_a11y_trend_html",
    "FailureCluster", "FailureClusterError",
    "cluster_failures", "normalise_error",
    "DriftReport", "PerfDriftError",
    "compute_drift", "detect_drift", "percentile",
    "BudgetCheckResult", "PerfBudgetError", "RouteBudget",
    "assert_within_budget", "evaluate_metrics", "load_budgets",
    "TrendDashboardError", "compute_trend", "render_run_trend_html",
]
