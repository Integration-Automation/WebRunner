"""Accessibility violations trend over time."""
from je_web_runner.utils.a11y_trend.trend import (
    A11yTrendError,
    A11yTrendPoint,
    aggregate_history,
    render_html,
)

__all__ = [
    "A11yTrendError",
    "A11yTrendPoint",
    "aggregate_history",
    "render_html",
]
