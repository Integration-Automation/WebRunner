"""
Test scheduling 最佳化:給 CI 分鐘 + cloud session 預算,挑出 value-density
最高的 test 子集合。

Inputs the scheduler can use:

* **duration_seconds** — average per-test wall time (from run_ledger /
  caller-supplied estimate).
* **fail_rate** — recent failure rate (from flake_detector or ledger).
  Higher fail rate → higher signal-per-minute.
* **impact_score** — likelihood the test touches code in this PR (from
  impact_analysis), 0..1.
* **last_run_age_hours** — how stale the most recent run is; older runs
  have higher information value.
* **manual_priority** — caller override for "always include".

The scheduler computes ``value = (fail_rate * 1.0 + impact_score * 1.5 +
last_run_age_hours / 24.0 + manual_priority * 2.0)``, divides by
``duration_seconds``, then greedily picks tests until the time budget
(or cloud quota) is exhausted. Cloud-only tests cost both budgets.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class TestSchedulerError(WebRunnerException):
    """Raised on invalid inputs or impossible budgets."""


# ---------- data ---------------------------------------------------------

@dataclass
class TestCandidate:
    """One test the scheduler can choose to run."""

    test_id: str
    duration_seconds: float
    fail_rate: float = 0.0
    impact_score: float = 0.0
    last_run_age_hours: float = 0.0
    manual_priority: float = 0.0
    needs_cloud_session: bool = False
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.test_id, str) or not self.test_id:
            raise TestSchedulerError("test_id must be a non-empty string")
        if self.duration_seconds <= 0:
            raise TestSchedulerError(
                f"duration_seconds must be > 0 for {self.test_id!r}, "
                f"got {self.duration_seconds}"
            )
        for name in ("fail_rate", "impact_score"):
            v = getattr(self, name)
            if v < 0 or v > 1:
                raise TestSchedulerError(
                    f"{name} must be in [0,1] for {self.test_id!r}, got {v}"
                )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Schedule:
    """Output of :func:`schedule_tests`."""

    selected: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    total_seconds: float = 0.0
    total_cloud_slots: int = 0
    leftover_seconds: float = 0.0
    leftover_cloud_slots: int = 0
    value_recovered: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------- value model --------------------------------------------------

_FAIL_WEIGHT = 1.0
_IMPACT_WEIGHT = 1.5
_AGE_DAY_WEIGHT = 1.0  # per 24h aged
_MANUAL_WEIGHT = 2.0


def value_of(candidate: TestCandidate) -> float:
    """Combined value score (higher = more worth running)."""
    return (
        candidate.fail_rate * _FAIL_WEIGHT
        + candidate.impact_score * _IMPACT_WEIGHT
        + (candidate.last_run_age_hours / 24.0) * _AGE_DAY_WEIGHT
        + candidate.manual_priority * _MANUAL_WEIGHT
    )


def value_density(candidate: TestCandidate) -> float:
    """Value per second — the greedy scheduler ranks by this."""
    return value_of(candidate) / candidate.duration_seconds


# ---------- scheduler ----------------------------------------------------

def schedule_tests(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    candidates: Sequence[TestCandidate],
    *,
    time_budget_seconds: float,
    cloud_slot_budget: Optional[int] = None,
    pinned_test_ids: Optional[Iterable[str]] = None,
) -> Schedule:
    """
    Greedy value-density schedule subject to time + cloud-slot budgets。
    ``pinned_test_ids`` are always included (if budget permits) regardless
    of value. Pinned tests that don't fit raise :class:`TestSchedulerError`
    so the caller knows their must-run set is too big.

    Note: greedy is not provably optimal (knapsack is NP-hard), but for
    test-suite scales (hundreds to thousands of tests) the gap to optimal
    is tiny and the algorithm is debuggable.
    """
    if time_budget_seconds <= 0:
        raise TestSchedulerError("time_budget_seconds must be > 0")
    if cloud_slot_budget is not None and cloud_slot_budget < 0:
        raise TestSchedulerError("cloud_slot_budget must be >= 0")
    pinned = set(pinned_test_ids or [])
    seen_ids = {c.test_id for c in candidates}
    missing = pinned - seen_ids
    if missing:
        raise TestSchedulerError(
            f"pinned test ids not in candidate set: {sorted(missing)}"
        )

    selected_ids: List[str] = []
    selected_cost = 0.0
    selected_cloud = 0
    value_recovered = 0.0
    seen_selected: set = set()

    # 1. Take pinned first, in input order so the user sees a stable list.
    for candidate in candidates:
        if candidate.test_id not in pinned:
            continue
        cost = candidate.duration_seconds
        cloud_cost = 1 if candidate.needs_cloud_session else 0
        if selected_cost + cost > time_budget_seconds:
            raise TestSchedulerError(
                f"pinned test {candidate.test_id!r} would overrun time budget"
            )
        if (cloud_slot_budget is not None and
                selected_cloud + cloud_cost > cloud_slot_budget):
            raise TestSchedulerError(
                f"pinned test {candidate.test_id!r} would overrun cloud slot budget"
            )
        selected_ids.append(candidate.test_id)
        seen_selected.add(candidate.test_id)
        selected_cost += cost
        selected_cloud += cloud_cost
        value_recovered += value_of(candidate)

    # 2. Greedy fill by value-density.
    ranked = sorted(
        (c for c in candidates if c.test_id not in seen_selected),
        key=lambda c: (-value_density(c), c.test_id),
    )
    for candidate in ranked:
        cost = candidate.duration_seconds
        cloud_cost = 1 if candidate.needs_cloud_session else 0
        if selected_cost + cost > time_budget_seconds:
            continue
        if (cloud_slot_budget is not None and
                selected_cloud + cloud_cost > cloud_slot_budget):
            continue
        selected_ids.append(candidate.test_id)
        seen_selected.add(candidate.test_id)
        selected_cost += cost
        selected_cloud += cloud_cost
        value_recovered += value_of(candidate)

    skipped = [c.test_id for c in candidates if c.test_id not in seen_selected]
    schedule = Schedule(
        selected=selected_ids,
        skipped=skipped,
        total_seconds=round(selected_cost, 2),
        total_cloud_slots=selected_cloud,
        leftover_seconds=round(time_budget_seconds - selected_cost, 2),
        leftover_cloud_slots=(
            -1 if cloud_slot_budget is None
            else cloud_slot_budget - selected_cloud
        ),
        value_recovered=round(value_recovered, 4),
    )
    web_runner_logger.info(
        f"schedule_tests: selected={len(selected_ids)}/{len(candidates)} "
        f"time={schedule.total_seconds}/{time_budget_seconds} "
        f"value={schedule.value_recovered:.2f}"
    )
    return schedule


# ---------- ledger / flake integration -----------------------------------

def build_candidates_from_ledger(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    ledger_path: Union[str, Path],
    *,
    default_duration_seconds: float = 60.0,
    fail_rate_lookup: Optional[Dict[str, float]] = None,
    impact_lookup: Optional[Dict[str, float]] = None,
    cloud_tests: Optional[Iterable[str]] = None,
    now_epoch: Optional[float] = None,
) -> List[TestCandidate]:
    """
    從 run_ledger 推每個 test 的 duration / fail_rate / last_run_age,
    再選擇性帶入 impact_score / cloud flag。
    Returns one :class:`TestCandidate` per distinct ``path`` in the ledger.
    """
    import time

    path = Path(ledger_path)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, ValueError) as error:
        raise TestSchedulerError(
            f"cannot read ledger {ledger_path}: {error!r}"
        ) from error
    runs = data.get("runs") if isinstance(data, dict) else None
    if not isinstance(runs, list):
        raise TestSchedulerError(f"ledger missing 'runs': {ledger_path}")
    now = now_epoch if now_epoch is not None else time.time()
    fail_rates = fail_rate_lookup or {}
    impacts = impact_lookup or {}
    cloud_set = set(cloud_tests or [])
    buckets: Dict[str, Dict[str, Any]] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        test_id = run.get("path")
        if not isinstance(test_id, str):
            continue
        record = buckets.setdefault(test_id, {
            "runs": 0, "fails": 0, "duration_sum": 0.0,
            "duration_count": 0, "latest_epoch": 0.0,
        })
        record["runs"] += 1
        if not run.get("passed"):
            record["fails"] += 1
        duration = run.get("duration_seconds")
        if isinstance(duration, (int, float)) and duration > 0:
            record["duration_sum"] += float(duration)
            record["duration_count"] += 1
        epoch = _parse_iso_epoch(run.get("time"))
        if epoch and epoch > record["latest_epoch"]:
            record["latest_epoch"] = epoch

    candidates: List[TestCandidate] = []
    for test_id, rec in buckets.items():
        avg_duration = (
            rec["duration_sum"] / rec["duration_count"]
            if rec["duration_count"] else default_duration_seconds
        )
        ledger_fail_rate = (rec["fails"] / rec["runs"]) if rec["runs"] else 0.0
        candidates.append(TestCandidate(
            test_id=test_id,
            duration_seconds=max(0.001, avg_duration),
            fail_rate=fail_rates.get(test_id, ledger_fail_rate),
            impact_score=impacts.get(test_id, 0.0),
            last_run_age_hours=(
                max(0.0, (now - rec["latest_epoch"]) / 3600.0)
                if rec["latest_epoch"] else 0.0
            ),
            needs_cloud_session=test_id in cloud_set,
        ))
    return candidates


def _parse_iso_epoch(value: Any) -> float:
    if not isinstance(value, str) or not value:
        return 0.0
    from datetime import datetime, timezone

    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return 0.0


# ---------- rendering ----------------------------------------------------

def render_schedule_markdown(schedule: Schedule) -> str:
    """Markdown view of the schedule for CI / PR comments."""
    pieces = [
        "## Test schedule",
        "",
        f"- **Selected:** {len(schedule.selected)}",
        f"- **Skipped:** {len(schedule.skipped)}",
        f"- **Total seconds:** {schedule.total_seconds}",
        f"- **Cloud slots used:** {schedule.total_cloud_slots}",
        f"- **Leftover seconds:** {schedule.leftover_seconds}",
        f"- **Value recovered:** {schedule.value_recovered}",
        "",
    ]
    if schedule.selected:
        pieces.append("### Selected tests (in run order)")
        for test_id in schedule.selected:
            pieces.append(f"- `{test_id}`")
        pieces.append("")
    if schedule.skipped:
        pieces.append("### Skipped tests")
        for test_id in schedule.skipped[:50]:
            pieces.append(f"- `{test_id}`")
        if len(schedule.skipped) > 50:
            pieces.append(f"- _(…and {len(schedule.skipped) - 50} more)_")
        pieces.append("")
    return "\n".join(pieces).rstrip() + "\n"
