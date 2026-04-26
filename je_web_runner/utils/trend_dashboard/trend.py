"""
從 run_ledger 拉資料，畫 pass-rate / duration / flake 趨勢線。
Build pass-rate / duration / flake-rate aggregates from the run ledger and
render them as a single self-contained HTML dashboard. Uses inline SVG so
the output is dependency-free and viewable offline.
"""
from __future__ import annotations

import html as _html
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class TrendDashboardError(WebRunnerException):
    """Raised when the ledger is missing or has an unexpected shape."""


@dataclass
class _Bucket:
    label: str
    passed: int = 0
    failed: int = 0
    total_duration: float = 0.0

    @property
    def total(self) -> int:
        return self.passed + self.failed

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def avg_duration(self) -> float:
        return self.total_duration / self.total if self.total else 0.0


def compute_trend(ledger_path: str) -> Dict[str, Any]:
    """
    依日期分桶，回傳 ``{daily: [...], totals: {...}}``
    Bucket the ledger by day and return per-day pass / fail / duration.
    """
    path = Path(ledger_path)
    if not path.is_file():
        raise TrendDashboardError(f"ledger not found: {ledger_path!r}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise TrendDashboardError(f"ledger not JSON: {error}") from error
    runs = data.get("runs")
    if not isinstance(runs, list):
        raise TrendDashboardError("ledger missing 'runs' list")
    buckets: Dict[str, _Bucket] = defaultdict(lambda: _Bucket(label="?"))
    for entry in runs:
        if not isinstance(entry, dict):
            continue
        timestamp = entry.get("time")
        day = _bucket_label(timestamp)
        bucket = buckets.setdefault(day, _Bucket(label=day))
        if entry.get("passed"):
            bucket.passed += 1
        else:
            bucket.failed += 1
        duration = entry.get("duration_seconds") or entry.get("duration") or 0
        try:
            bucket.total_duration += float(duration)
        except (TypeError, ValueError):
            pass
    daily = sorted(buckets.values(), key=lambda b: b.label)
    return {
        "daily": [
            {
                "label": b.label,
                "passed": b.passed,
                "failed": b.failed,
                "total": b.total,
                "pass_rate": b.pass_rate,
                "avg_duration_seconds": b.avg_duration,
            }
            for b in daily
        ],
        "totals": {
            "passed": sum(b.passed for b in daily),
            "failed": sum(b.failed for b in daily),
            "total": sum(b.total for b in daily),
            "pass_rate": (
                sum(b.passed for b in daily) / max(1, sum(b.total for b in daily))
            ),
        },
    }


def _bucket_label(timestamp: Optional[str]) -> str:
    if not isinstance(timestamp, str):
        return "unknown"
    try:
        return datetime.fromisoformat(timestamp).strftime("%Y-%m-%d")
    except ValueError:
        return timestamp[:10] if len(timestamp) >= 10 else "unknown"


def render_html(trend: Dict[str, Any], title: str = "WebRunner trend") -> str:
    """Render a self-contained HTML dashboard from :func:`compute_trend`."""
    daily = trend.get("daily") or []
    rows: List[str] = []
    for entry in daily:
        rows.append(
            f"<tr><td>{_html.escape(entry['label'])}</td>"
            f"<td>{entry['total']}</td>"
            f"<td>{entry['passed']}</td>"
            f"<td>{entry['failed']}</td>"
            f"<td>{entry['pass_rate'] * 100:.1f}%</td>"
            f"<td>{entry['avg_duration_seconds']:.2f}s</td></tr>"
        )
    svg = _render_pass_rate_svg(daily)
    body = f"""
    <html><head><meta charset='utf-8'><title>{_html.escape(title)}</title>
    <style>
      body{{font-family:-apple-system,Segoe UI,sans-serif;max-width:920px;margin:2rem auto;}}
      table{{border-collapse:collapse;width:100%;margin-top:1rem;}}
      th,td{{border:1px solid #ccc;padding:.4rem .6rem;text-align:left;}}
      th{{background:#f4f4f4;}}
    </style></head>
    <body>
      <h1>{_html.escape(title)}</h1>
      {svg}
      <table>
        <thead><tr><th>Date</th><th>Total</th><th>Passed</th><th>Failed</th>
        <th>Pass rate</th><th>Avg duration</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </body></html>
    """
    return body


def _render_pass_rate_svg(daily: List[Dict[str, Any]]) -> str:
    if not daily:
        return "<p><em>No runs recorded yet.</em></p>"
    width = 720
    height = 200
    margin = 30
    plot_w = width - 2 * margin
    plot_h = height - 2 * margin
    n = len(daily)
    if n == 1:
        x_step = 0
    else:
        x_step = plot_w / (n - 1)
    points = []
    for i, entry in enumerate(daily):
        x = margin + i * x_step
        y = margin + (1 - entry["pass_rate"]) * plot_h
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    axis = (
        f"<line x1='{margin}' y1='{margin + plot_h}' "
        f"x2='{margin + plot_w}' y2='{margin + plot_h}' stroke='#888'/>"
        f"<line x1='{margin}' y1='{margin}' x2='{margin}' y2='{margin + plot_h}' stroke='#888'/>"
    )
    return (
        f"<svg width='{width}' height='{height}' xmlns='http://www.w3.org/2000/svg'>"
        f"{axis}"
        f"<polyline points='{polyline}' fill='none' stroke='#0a7' stroke-width='2'/>"
        f"</svg>"
    )


def write_dashboard(trend: Dict[str, Any], output_path: str,
                    title: str = "WebRunner trend") -> Path:
    text = render_html(trend, title=title)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target
