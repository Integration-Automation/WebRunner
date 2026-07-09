"""
Interaction to Next Paint (INP) tracker。INP 是 Google 2024 取代 FID 的
Core Web Vital,衡量「使用者點 / 鍵盤輸入 / tap → 下次 paint」的延遲。

This module:

* Generates a JS snippet that uses the ``event-timing`` PerformanceObserver
  to record every interaction's duration into ``window.__wr_inp_log__``.
* Parses the harvested array.
* Reports per-interaction breakdown + p75 / p98 percentiles (the
  thresholds Google uses for "good" / "poor").
* Asserts page-level budget.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class InpTrackerError(WebRunnerException):
    """Raised on malformed log input or budget breach."""


class InpRating(str, Enum):
    """Google's INP rating thresholds."""

    GOOD = "good"        # <= 200ms
    NEEDS_WORK = "needs_improvement"  # 201..500ms
    POOR = "poor"        # > 500ms


_GOOD_THRESHOLD_MS = 200.0
_POOR_THRESHOLD_MS = 500.0


# ---------- instrumentation -------------------------------------------

_INSTALL = """
(function() {
  if (window.__wr_inp_installed__) return;
  window.__wr_inp_installed__ = true;
  window.__wr_inp_log__ = [];
  if (!('PerformanceObserver' in window)) return;
  try {
    const obs = new PerformanceObserver(function(list) {
      list.getEntries().forEach(function(entry) {
        if (entry.duration === undefined) return;
        window.__wr_inp_log__.push({
          name: entry.name,
          interactionId: entry.interactionId || 0,
          duration_ms: entry.duration,
          processingStart: entry.processingStart,
          processingEnd: entry.processingEnd,
          startTime: entry.startTime,
          targetTag: entry.target ? entry.target.tagName : null
        });
      });
    });
    obs.observe({type: 'event', buffered: true, durationThreshold: 16});
    obs.observe({type: 'first-input', buffered: true});
  } catch (e) { /* unsupported */ }
})();
""".strip()


def build_install_script() -> str:
    return _INSTALL


HARVEST_SCRIPT = "return window.__wr_inp_log__ || [];"


# ---------- data --------------------------------------------------------

@dataclass
class InteractionEvent:
    """One event-timing entry."""

    name: str
    interaction_id: int
    duration_ms: float
    target_tag: str | None = None
    start_time: float = 0.0
    processing_start: float = 0.0
    processing_end: float = 0.0

    def rating(self) -> InpRating:
        return _rate(self.duration_ms)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "rating": self.rating().value}


def _rate(duration_ms: float) -> InpRating:
    if duration_ms <= _GOOD_THRESHOLD_MS:
        return InpRating.GOOD
    if duration_ms <= _POOR_THRESHOLD_MS:
        return InpRating.NEEDS_WORK
    return InpRating.POOR


def parse_log(payload: Any) -> list[InteractionEvent]:
    """Convert the harvested ``__wr_inp_log__`` array into typed events."""
    if not isinstance(payload, list):
        raise InpTrackerError(
            f"payload must be list, got {type(payload).__name__}"
        )
    out: list[InteractionEvent] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        try:
            duration = float(raw.get("duration_ms") or 0.0)
        except (TypeError, ValueError):
            continue
        if duration < 0:
            continue
        out.append(InteractionEvent(
            name=str(raw.get("name") or ""),
            interaction_id=int(raw.get("interactionId") or 0),
            duration_ms=duration,
            target_tag=raw.get("targetTag"),
            start_time=float(raw.get("startTime") or 0.0),
            processing_start=float(raw.get("processingStart") or 0.0),
            processing_end=float(raw.get("processingEnd") or 0.0),
        ))
    return out


# ---------- aggregation ------------------------------------------------

@dataclass
class InpReport:
    """Rolled-up view of the events captured in a page session."""

    events: list[InteractionEvent] = field(default_factory=list)

    def filtered(self) -> list[InteractionEvent]:
        """Discard zero-id non-interaction entries (mouse-move, raw events)."""
        return [e for e in self.events if e.interaction_id > 0]

    def inp(self) -> float | None:
        """
        Returns Google's INP: 98th percentile if 50+ interactions, else worst.
        ``None`` if no interactions observed.
        """
        interactions = sorted(e.duration_ms for e in self.filtered())
        if not interactions:
            return None
        if len(interactions) >= 50:
            index = int(round(0.98 * (len(interactions) - 1)))
            return interactions[index]
        return interactions[-1]

    def rating(self) -> InpRating:
        value = self.inp()
        if value is None:
            return InpRating.GOOD
        return _rate(value)

    def percentile(self, pct: float) -> float | None:
        """Arbitrary percentile (0..100) over interaction durations."""
        if not 0 <= pct <= 100:
            raise InpTrackerError("pct must be in [0, 100]")
        interactions = sorted(e.duration_ms for e in self.filtered())
        if not interactions:
            return None
        index = int(round((pct / 100.0) * (len(interactions) - 1)))
        return interactions[index]


# ---------- assertions -------------------------------------------------

def assert_inp_under(report: InpReport, *, max_ms: float) -> None:
    """Assert the report's INP is under ``max_ms``."""
    if not isinstance(report, InpReport):
        raise InpTrackerError("assert_inp_under expects InpReport")
    if max_ms <= 0:
        raise InpTrackerError("max_ms must be > 0")
    value = report.inp()
    if value is None:
        return
    if value > max_ms:
        raise InpTrackerError(
            f"INP {value:.1f}ms exceeds budget {max_ms}ms "
            f"({report.rating().value})"
        )


def assert_no_poor_interactions(report: InpReport) -> None:
    """Assert no single interaction crossed the POOR threshold."""
    if not isinstance(report, InpReport):
        raise InpTrackerError("expects InpReport")
    bad = [e for e in report.filtered() if e.rating() == InpRating.POOR]
    if bad:
        sample = ", ".join(f"{e.name}({e.duration_ms:.0f}ms)" for e in bad[:3])
        more = "" if len(bad) <= 3 else f" (+{len(bad) - 3} more)"
        raise InpTrackerError(f"poor interactions: {sample}{more}")
