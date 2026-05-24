"""
重複跑同一個失敗 test N 次,報告重現率 — 區分 deterministic vs flaky bug。
When triaging a regression, the first question is "does this always
break, or just sometimes?". This module runs the test N times via a
caller-supplied runner and rolls up:

* repro percentage
* longest pass / fail streak
* category: deterministic / flaky / non_reproducible
* per-error grouping (e.g. all failures hit the same exception line)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


_EXPECTS_REPORT_MSG = "expects StabilityReport"


class BugReproStabilityError(WebRunnerException):
    """Raised on bad inputs or runner failure."""


class ReproCategory(str, Enum):
    DETERMINISTIC = "deterministic"  # 100% repro
    FLAKY = "flaky"                  # 1..99% repro
    NON_REPRODUCIBLE = "non_reproducible"  # 0% repro


# ---------- runner contract -------------------------------------------

@dataclass
class RunOutcome:
    """One probe outcome."""

    passed: bool
    error_signature: Optional[str] = None
    duration_seconds: float = 0.0


ProbeFn = Callable[[int], RunOutcome]
"""``probe(attempt_index) -> RunOutcome``."""


# ---------- report ----------------------------------------------------

@dataclass
class StabilityReport:
    """Roll-up of N attempts."""

    attempts: int
    failures: int
    repro_pct: float
    category: ReproCategory
    longest_pass_streak: int = 0
    longest_fail_streak: int = 0
    errors: Dict[str, int] = field(default_factory=dict)
    durations: List[float] = field(default_factory=list)

    def passed(self) -> bool:
        return self.category == ReproCategory.NON_REPRODUCIBLE

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "category": self.category.value}


def _classify(repro_pct: float) -> ReproCategory:
    if repro_pct >= 100.0:
        return ReproCategory.DETERMINISTIC
    if repro_pct <= 0.0:
        return ReproCategory.NON_REPRODUCIBLE
    return ReproCategory.FLAKY

# ---------- core -------------------------------------------------------

@dataclass
class _StreakState:
    """Mutable counters carried across iterations of :func:`repeat`."""

    failures: int = 0
    longest_pass: int = 0
    longest_fail: int = 0
    pass_streak: int = 0
    fail_streak: int = 0


def _probe_once(probe: ProbeFn, index: int) -> RunOutcome:
    try:
        outcome = probe(index)
    except Exception as error:
        raise BugReproStabilityError(
            f"probe raised at attempt {index}: {error!r}"
        ) from error
    if not isinstance(outcome, RunOutcome):
        raise BugReproStabilityError(
            f"probe must return RunOutcome, got {type(outcome).__name__}"
        )
    return outcome


def _record_outcome(
    outcome: RunOutcome, state: _StreakState, errors: Dict[str, int],
) -> None:
    if outcome.passed:
        state.pass_streak += 1
        state.fail_streak = 0
        state.longest_pass = max(state.longest_pass, state.pass_streak)
    else:
        state.failures += 1
        state.fail_streak += 1
        state.pass_streak = 0
        state.longest_fail = max(state.longest_fail, state.fail_streak)
        sig = outcome.error_signature or "(unspecified)"
        errors[sig] = errors.get(sig, 0) + 1


def repeat(
    probe: ProbeFn,
    *,
    attempts: int = 10,
    stop_on_first_failure: bool = False,
    stop_on_first_pass: bool = False,
) -> StabilityReport:
    """
    Drive ``probe`` ``attempts`` times, return :class:`StabilityReport`.
    Set ``stop_on_first_failure=True`` to short-circuit when only
    confirming whether the bug *ever* repros.
    """
    if not callable(probe):
        raise BugReproStabilityError("probe must be callable")
    if attempts <= 0:
        raise BugReproStabilityError("attempts must be > 0")

    state = _StreakState()
    errors: Dict[str, int] = {}
    durations: List[float] = []
    actual_attempts = 0
    for index in range(attempts):
        actual_attempts += 1
        outcome = _probe_once(probe, index)
        durations.append(outcome.duration_seconds)
        _record_outcome(outcome, state, errors)
        if outcome.passed and stop_on_first_pass:
            break
        if not outcome.passed and stop_on_first_failure:
            break
        web_runner_logger.debug(
            f"bug_repro_stability attempt {index + 1}/{attempts}: "
            f"passed={outcome.passed}"
        )
    repro_pct = (state.failures / actual_attempts) * 100.0
    return StabilityReport(
        attempts=actual_attempts,
        failures=state.failures,
        repro_pct=round(repro_pct, 2),
        category=_classify(repro_pct),
        longest_pass_streak=state.longest_pass,
        longest_fail_streak=state.longest_fail,
        errors=errors,
        durations=[round(d, 4) for d in durations],
    )


# ---------- assertions -------------------------------------------------

def assert_deterministic(report: StabilityReport) -> None:
    """Raise unless the report is :attr:`ReproCategory.DETERMINISTIC`."""
    if not isinstance(report, StabilityReport):
        raise BugReproStabilityError(_EXPECTS_REPORT_MSG)
    if report.category != ReproCategory.DETERMINISTIC:
        raise BugReproStabilityError(
            f"expected deterministic repro, got {report.category.value} "
            f"({report.repro_pct:.1f}%)"
        )


def assert_min_repro_pct(report: StabilityReport, *, minimum: float) -> None:
    """Assert ``report.repro_pct >= minimum``."""
    if not isinstance(report, StabilityReport):
        raise BugReproStabilityError(_EXPECTS_REPORT_MSG)
    if not 0 <= minimum <= 100:
        raise BugReproStabilityError("minimum must be in [0, 100]")
    if report.repro_pct < minimum:
        raise BugReproStabilityError(
            f"repro {report.repro_pct:.1f}% below threshold {minimum:.1f}%"
        )


# ---------- formatting -------------------------------------------------

def report_markdown(report: StabilityReport) -> str:
    """Render a compact markdown summary."""
    if not isinstance(report, StabilityReport):
        raise BugReproStabilityError(_EXPECTS_REPORT_MSG)
    avg = sum(report.durations) / len(report.durations) if report.durations else 0.0
    lines = [
        f"### Repro stability: **{report.category.value}** "
        f"({report.failures}/{report.attempts} = {report.repro_pct:.1f}%)",
        "",
        f"- longest fail streak: {report.longest_fail_streak}",
        f"- longest pass streak: {report.longest_pass_streak}",
        f"- avg attempt duration: {avg:.2f}s",
    ]
    if report.errors:
        lines.append("")
        lines.append("**Error signatures:**")
        for sig, count in sorted(report.errors.items(), key=lambda kv: -kv[1]):
            lines.append(f"- `{sig}` × {count}")
    return "\n".join(lines) + "\n"
