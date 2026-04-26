"""Pass-rate / duration trends pulled from the run ledger."""
from je_web_runner.utils.trend_dashboard.trend import (
    TrendDashboardError,
    compute_trend,
    render_html,
)

__all__ = ["TrendDashboardError", "compute_trend", "render_html"]
