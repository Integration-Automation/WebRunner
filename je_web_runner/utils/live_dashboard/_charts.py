"""
儀表板的 SVG 圖表 / Inline SVG charts for the dashboard.

Plain SVG with presentation classes (styled by the same-origin stylesheet), so it
works under the pages' CSP and needs no chart library.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.live_dashboard._widgets import html_escape

_WIDTH, _HEIGHT = 1000, 260
_LEFT, _RIGHT, _TOP, _BOTTOM = 48, 16, 14, 30
_INSET = 24  # keeps the first and last day's bar clear of the axis labels
_PLOT_W = _WIDTH - _LEFT - _RIGHT
_PLOT_H = _HEIGHT - _TOP - _BOTTOM


def _x(index: int, count: int) -> float:
    span = _PLOT_W - 2 * _INSET
    return _LEFT + _INSET + (span / 2 if count == 1 else span * index / (count - 1))


def _y(rate: float) -> float:
    return _TOP + _PLOT_H * (1 - rate)


def _grid() -> str:
    lines = []
    for rate in (0.0, 0.5, 1.0):
        y = _y(rate)
        lines.append(
            f"<line class='grid' x1='{_LEFT}' y1='{y:.1f}' x2='{_WIDTH - _RIGHT}' y2='{y:.1f}'/>"
            f"<text class='axis' x='{_LEFT - 6}' y='{y + 4:.1f}' text-anchor='end'>{int(rate * 100)}%</text>"
        )
    return "".join(lines)


def _fail_bars(days: list[dict[str, Any]]) -> str:
    most = max((day["failed"] for day in days), default=0)
    if not most:
        return ""
    width = max(2.0, min(18.0, _PLOT_W / max(len(days), 1) * 0.5))
    bars = []
    for index, day in enumerate(days):
        height = _PLOT_H * 0.35 * day["failed"] / most
        x = _x(index, len(days)) - width / 2
        bars.append(
            f"<rect class='fail' x='{x:.1f}' y='{_TOP + _PLOT_H - height:.1f}' "
            f"width='{width:.1f}' height='{height:.1f}'/>"
        )
    return "".join(bars)


def _anchor(index: int, count: int) -> str:
    if count == 1:
        return "middle"
    if index == 0:
        return "start"
    return "end" if index == count - 1 else "middle"


def _x_labels(days: list[dict[str, Any]]) -> str:
    count = len(days)
    picks = sorted({0, count // 2, count - 1})
    return "".join(
        f"<text class='axis' x='{_x(index, count):.1f}' y='{_HEIGHT - 8}' text-anchor='{_anchor(index, count)}'>"
        f"{html_escape(days[index]['label'])}</text>"
        for index in picks
    )


def pass_rate_chart(daily: list[dict[str, Any]]) -> str:
    """
    每日通過率折線加失敗數長條
    Daily pass rate as a line (0–100 %) over bars of each day's failure count, from
    :func:`~je_web_runner.utils.trend_dashboard.trend.compute_trend_from_runs` buckets.
    Days without a date (``unknown``) are left out. Empty string when there is nothing to draw.
    """
    days = [day for day in daily if day.get("label") != "unknown" and day.get("total")]
    if not days:
        return ""
    points = [(_x(i, len(days)), _y(float(day["pass_rate"]))) for i, day in enumerate(days)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    base = _y(0.0)
    area = f"{points[0][0]:.1f},{base:.1f} {line} {points[-1][0]:.1f},{base:.1f}"
    dots = "".join(
        f"<circle class='dot' cx='{x:.1f}' cy='{y:.1f}' r='3.5'><title>"
        f"{html_escape(day['label'])}: {day['pass_rate'] * 100:.1f}% passed "
        f"({day['passed']}/{day['total']}), {day['failed']} failed</title></circle>"
        for (x, y), day in zip(points, days)
    )
    return (
        f"<svg class='chart' viewBox='0 0 {_WIDTH} {_HEIGHT}' role='img' "
        f"aria-label='Daily pass rate over {len(days)} days'>"
        f"{_grid()}{_fail_bars(days)}"
        f"<polygon class='area' points='{area}'/><polyline class='line' points='{line}'/>"
        f"{dots}{_x_labels(days)}</svg>"
    )
