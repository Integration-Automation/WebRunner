"""
Quarantine 條目加上 age + 自動 escalation tier。
After ``flake_detector`` puts a test in quarantine the *real* danger is
it sits there forever. This module reads the quarantine registry,
computes how long each entry has been parked, and assigns an escalation
tier so dashboards can highlight "this has been quarantined 90+ days,
delete or fix it".
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class QuarantineAgeReportError(WebRunnerException):
    """Raised on malformed registry / inputs."""


class EscalationTier(str, Enum):
    """How urgently each quarantined test needs attention."""

    FRESH = "fresh"      # < 7 days
    LINGERING = "lingering"  # 7..30 days
    STALE = "stale"      # 30..90 days
    ABANDONED = "abandoned"  # >= 90 days


_TIER_THRESHOLDS = (
    (7, EscalationTier.FRESH),
    (30, EscalationTier.LINGERING),
    (90, EscalationTier.STALE),
)


@dataclass
class AgedEntry:
    """One quarantine entry + escalation metadata."""

    test_id: str
    reason: str
    flake_score: float
    quarantined_at: str
    age_days: float
    tier: EscalationTier
    triage_url: Optional[str] = None
    runs_when_added: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "tier": self.tier.value}


@dataclass
class AgeReport:
    """Roll-up over a whole quarantine registry."""

    total_entries: int = 0
    by_tier: Dict[str, int] = field(default_factory=dict)
    entries: List[AgedEntry] = field(default_factory=list)
    abandoned: List[str] = field(default_factory=list)


def _parse_iso(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise QuarantineAgeReportError("timestamp must be a non-empty string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as error:
        raise QuarantineAgeReportError(f"bad timestamp {value!r}: {error}") from error
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _tier_for(age_days: float) -> EscalationTier:
    for threshold, tier in _TIER_THRESHOLDS:
        if age_days < threshold:
            return tier
    return EscalationTier.ABANDONED


def _load_registry(path: Union[str, Path]) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise QuarantineAgeReportError(f"registry not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as error:
        raise QuarantineAgeReportError(f"registry not JSON: {error}") from error
    if not isinstance(data, dict) or "entries" not in data:
        raise QuarantineAgeReportError("registry missing 'entries' key")
    entries = data["entries"]
    if not isinstance(entries, list):
        raise QuarantineAgeReportError("registry 'entries' must be a list")
    return entries


def age_entries(
    entries: Sequence[Dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> List[AgedEntry]:
    """Convert raw registry rows into typed entries with age + tier."""
    moment = now if now is not None else datetime.now(tz=timezone.utc)
    if moment.tzinfo is None:
        raise QuarantineAgeReportError("now must be tz-aware")
    out: List[AgedEntry] = []
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        test_id = raw.get("test_id")
        if not isinstance(test_id, str) or not test_id:
            continue
        timestamp = raw.get("quarantined_at")
        if not isinstance(timestamp, str) or not timestamp:
            continue
        added = _parse_iso(timestamp)
        age_days = max(0.0, (moment - added).total_seconds() / 86400.0)
        out.append(AgedEntry(
            test_id=test_id,
            reason=str(raw.get("reason") or ""),
            flake_score=float(raw.get("flake_score") or 0.0),
            quarantined_at=timestamp,
            age_days=round(age_days, 2),
            tier=_tier_for(age_days),
            triage_url=raw.get("triage_url"),
            runs_when_added=int(raw.get("runs_when_added") or 0),
        ))
    return out


def build_report(entries: Iterable[AgedEntry]) -> AgeReport:
    """Aggregate a list of aged entries into a :class:`AgeReport`."""
    report = AgeReport()
    for entry in entries:
        if not isinstance(entry, AgedEntry):
            raise QuarantineAgeReportError(
                f"expects AgedEntry, got {type(entry).__name__}"
            )
        report.total_entries += 1
        tier = entry.tier.value
        report.by_tier[tier] = report.by_tier.get(tier, 0) + 1
        report.entries.append(entry)
        if entry.tier == EscalationTier.ABANDONED:
            report.abandoned.append(entry.test_id)
    return report


def load_and_age(
    registry_path: Union[str, Path],
    *,
    now: Optional[datetime] = None,
) -> AgeReport:
    """One-shot: load JSON registry, age every row, build report."""
    return build_report(age_entries(_load_registry(registry_path), now=now))


# ---------- formatting ------------------------------------------------

def report_markdown(report: AgeReport, *, top_n: int = 10) -> str:
    """Render a small markdown summary suitable for dashboards / PR comments."""
    if not isinstance(report, AgeReport):
        raise QuarantineAgeReportError("expects AgeReport")
    if top_n < 0:
        raise QuarantineAgeReportError("top_n must be >= 0")
    lines = [
        f"### Quarantine age report ({report.total_entries} entries)",
        "",
    ]
    if report.by_tier:
        lines.append("| Tier | Count |")
        lines.append("|------|-------|")
        for tier in EscalationTier:
            count = report.by_tier.get(tier.value, 0)
            lines.append(f"| {tier.value} | {count} |")
    if report.abandoned:
        lines.append("")
        lines.append("**Abandoned (90+ days):**")
        for tid in report.abandoned[:top_n]:
            lines.append(f"- `{tid}`")
        if len(report.abandoned) > top_n:
            lines.append(f"- _+{len(report.abandoned) - top_n} more_")
    return "\n".join(lines) + "\n"


def assert_no_abandoned(report: AgeReport) -> None:
    """Raise if any test has been quarantined past the ABANDONED threshold."""
    if not isinstance(report, AgeReport):
        raise QuarantineAgeReportError("expects AgeReport")
    if not report.abandoned:
        return
    sample = ", ".join(report.abandoned[:5])
    more = "" if len(report.abandoned) <= 5 else f" (+{len(report.abandoned) - 5})"
    raise QuarantineAgeReportError(
        f"{len(report.abandoned)} abandoned quarantine entries: {sample}{more}"
    )
