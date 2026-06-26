"""
SLA 達成率追蹤:「Y% 的 suite 在 X 分鐘內跑完」加趨勢。
Engineering teams set targets like "95% of CI runs finish in under 10
minutes" but rarely have a number to point at. This module reads the
run ledger, groups by ISO week, and computes the rolling SLA-met
percentage so dashboards can show "we're at 91% this week, down from
97% two weeks ago, that's the regression".
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SlaTrackerError(WebRunnerException):
    """Raised on bad ledger / SLA inputs."""


# ---------- input ------------------------------------------------------

@dataclass
class SuiteRun:
    """One suite run."""

    suite: str
    started_at: datetime
    duration_seconds: float
    passed: bool

    def __post_init__(self) -> None:
        if not isinstance(self.suite, str) or not self.suite:
            raise SlaTrackerError("suite must be non-empty string")
        if self.duration_seconds < 0:
            raise SlaTrackerError("duration_seconds must be >= 0")
        if not isinstance(self.started_at, datetime):
            raise SlaTrackerError("started_at must be datetime")
        if self.started_at.tzinfo is None:
            raise SlaTrackerError("started_at must be tz-aware")


def _parse_iso(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as error:
        raise SlaTrackerError(f"bad timestamp {value!r}: {error}") from error
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_runs(path: str | Path) -> list[SuiteRun]:
    """Read a ledger JSON file. Skips rows missing the fields we need."""
    p = Path(path)
    if not p.exists():
        raise SlaTrackerError(f"ledger not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as error:
        raise SlaTrackerError(f"ledger not JSON: {error}") from error
    if not isinstance(data, dict) or "runs" not in data:
        raise SlaTrackerError("ledger missing 'runs' key")
    out: list[SuiteRun] = []
    for raw in data["runs"]:
        if not isinstance(raw, dict):
            continue
        suite = raw.get("suite") or raw.get("path")
        timestamp = raw.get("time") or raw.get("started_at")
        duration = raw.get("duration_seconds")
        if not isinstance(suite, str) or duration is None or not isinstance(timestamp, str):
            continue
        try:
            run = SuiteRun(
                suite=suite,
                started_at=_parse_iso(timestamp),
                duration_seconds=float(duration),
                passed=bool(raw.get("passed", True)),
            )
        except SlaTrackerError:
            continue
        out.append(run)
    return out


# ---------- SLA model --------------------------------------------------

@dataclass(frozen=True)
class SlaTarget:
    """Definition of the SLA."""

    max_duration_seconds: float
    target_pass_pct: float

    def __post_init__(self) -> None:
        if self.max_duration_seconds <= 0:
            raise SlaTrackerError("max_duration_seconds must be > 0")
        if not 0 < self.target_pass_pct <= 100:
            raise SlaTrackerError("target_pass_pct must be in (0, 100]")


@dataclass
class BucketResult:
    """One bucket (week or day) of SLA stats."""

    label: str
    runs: int
    met: int
    pct: float
    target_met: bool


@dataclass
class SlaReport:
    """Outcome of :func:`compute_sla`."""

    target: SlaTarget
    buckets: list[BucketResult] = field(default_factory=list)
    overall_pct: float = 0.0
    overall_runs: int = 0

    def passed(self) -> bool:
        return self.overall_pct >= self.target.target_pass_pct

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": asdict(self.target),
            "buckets": [asdict(b) for b in self.buckets],
            "overall_pct": self.overall_pct,
            "overall_runs": self.overall_runs,
            "passed": self.passed(),
        }


# ---------- bucketing --------------------------------------------------

def _week_label(dt: datetime) -> str:
    iso = dt.isocalendar()
    return f"{iso[0]:04d}-W{iso[1]:02d}"


def _day_label(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def compute_sla(
    runs: Sequence[SuiteRun],
    target: SlaTarget,
    *,
    bucket: str = "week",
    suite: str | None = None,
) -> SlaReport:
    """Group runs into buckets, compute met-percentage, aggregate."""
    if bucket not in ("week", "day"):
        raise SlaTrackerError("bucket must be 'week' or 'day'")
    label_fn = _week_label if bucket == "week" else _day_label
    buckets_by_label: dict[str, list[SuiteRun]] = {}
    for run in runs:
        if not isinstance(run, SuiteRun):
            raise SlaTrackerError(
                f"runs entry must be SuiteRun, got {type(run).__name__}"
            )
        if suite is not None and run.suite != suite:
            continue
        buckets_by_label.setdefault(label_fn(run.started_at), []).append(run)
    bucket_results: list[BucketResult] = []
    total_runs = 0
    total_met = 0
    for label in sorted(buckets_by_label):
        runs_in_bucket = buckets_by_label[label]
        met = sum(1 for r in runs_in_bucket
                  if r.duration_seconds <= target.max_duration_seconds)
        pct = (met / len(runs_in_bucket)) * 100.0
        bucket_results.append(BucketResult(
            label=label,
            runs=len(runs_in_bucket),
            met=met,
            pct=round(pct, 2),
            target_met=pct >= target.target_pass_pct,
        ))
        total_runs += len(runs_in_bucket)
        total_met += met
    overall_pct = (total_met / total_runs * 100.0) if total_runs else 0.0
    return SlaReport(
        target=target,
        buckets=bucket_results,
        overall_pct=round(overall_pct, 2),
        overall_runs=total_runs,
    )


# ---------- formatting -------------------------------------------------

def report_markdown(report: SlaReport) -> str:
    """Render a small markdown table for dashboards / Slack."""
    if not isinstance(report, SlaReport):
        raise SlaTrackerError("expects SlaReport")
    lines = [
        f"### SLA: {report.target.target_pass_pct:.0f}% of suites in "
        f"<= {report.target.max_duration_seconds:.0f}s",
        "",
        f"- Overall: **{report.overall_pct:.1f}%** "
        f"({report.overall_runs} runs)",
        "",
        "| Bucket | Runs | Met | % |",
        "|--------|------|-----|---|",
    ]
    for b in report.buckets:
        mark = "✓" if b.target_met else "✗"
        lines.append(f"| {b.label} | {b.runs} | {b.met} | {b.pct:.1f}% {mark} |")
    return "\n".join(lines) + "\n"


def assert_meets_sla(report: SlaReport) -> None:
    """Raise if the overall percentage is below the target."""
    if not isinstance(report, SlaReport):
        raise SlaTrackerError("expects SlaReport")
    if report.passed():
        return
    raise SlaTrackerError(
        f"SLA breach: {report.overall_pct:.1f}% < target "
        f"{report.target.target_pass_pct:.1f}% "
        f"({report.overall_runs} runs)"
    )
