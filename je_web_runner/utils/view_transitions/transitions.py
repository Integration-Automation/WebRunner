"""
驗證 View Transitions API 動畫順利完成且未造成 layout shift。
The ``document.startViewTransition`` API is great UX but easy to break:
the ``::view-transition-group`` pseudo-elements stall, throw, or trigger
a CLS spike when underlying layout shifts.

This module:

* Generates the JS snippet to *instrument* a page (one-time injection)
  that records each transition's lifecycle into ``window.__wr_vt_log__``
  and observes ``LayoutShift`` entries scoped to the transition window.
* Parses the harvested log into :class:`TransitionRun` records.
* Exposes asserts for duration budget, CLS budget, error-free run,
  expected element-name presence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ViewTransitionsError(WebRunnerException):
    """Raised on bad input, missing log, or failed assertion."""


# ---------- instrumentation -------------------------------------------

_INSTRUMENT_JS = """
(function() {
  if (window.__wr_vt_installed__) return;
  window.__wr_vt_installed__ = true;
  window.__wr_vt_log__ = [];
  const _start = document.startViewTransition
    ? document.startViewTransition.bind(document)
    : null;
  if (!_start) return;

  function track(promise, key) {
    promise.then(
      function() {
        const entry = window.__wr_vt_log__.find(e => e.id === key);
        if (entry) {
          entry[key === entry.id && '__finished_at__'] = performance.now();
        }
      },
      function(err) {
        const entry = window.__wr_vt_log__.find(e => e.id === key);
        if (entry) {
          entry.error = String(err && err.message || err);
          entry.__finished_at__ = performance.now();
        }
      }
    );
  }

  document.startViewTransition = function(callback) {
    const id = 'vt_' + (window.__wr_vt_log__.length + 1);
    const startedAt = performance.now();
    const entry = {
      id: id,
      startedAt: startedAt,
      finishedAt: null,
      durationMs: null,
      error: null,
      layoutShifts: 0,
      maxShiftValue: 0,
      groups: []
    };
    window.__wr_vt_log__.push(entry);

    let cumulative = 0;
    let maxShift = 0;
    const obs = new PerformanceObserver(function(list) {
      list.getEntries().forEach(function(s) {
        if (!s.hadRecentInput) {
          cumulative += s.value;
          if (s.value > maxShift) maxShift = s.value;
        }
      });
    });
    try { obs.observe({type: 'layout-shift', buffered: false}); } catch (e) {}

    const transition = _start(callback);
    transition.finished.then(function() {
      try { obs.disconnect(); } catch (e) {}
      entry.finishedAt = performance.now();
      entry.durationMs = entry.finishedAt - entry.startedAt;
      entry.layoutShifts = cumulative;
      entry.maxShiftValue = maxShift;
    }, function(err) {
      try { obs.disconnect(); } catch (e) {}
      entry.finishedAt = performance.now();
      entry.durationMs = entry.finishedAt - entry.startedAt;
      entry.error = String(err && err.message || err);
    });
    return transition;
  };
})();
""".strip()


def build_instrumentation_script() -> str:
    """Return the JS snippet to install via CDP/Playwright add-init-script."""
    return _INSTRUMENT_JS


# ---------- data --------------------------------------------------------

@dataclass
class TransitionRun:
    """One ``startViewTransition`` call's outcome."""

    id: str
    started_at: float
    finished_at: Optional[float] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    layout_shifts: float = 0.0
    max_shift_value: float = 0.0
    groups: List[str] = field(default_factory=list)

    def is_finished(self) -> bool:
        return self.finished_at is not None and self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_log(log: Sequence[Dict[str, Any]]) -> List[TransitionRun]:
    """Convert the harvested ``window.__wr_vt_log__`` array into typed runs."""
    if not isinstance(log, list):
        raise ViewTransitionsError(
            f"parse_log expects list, got {type(log).__name__}"
        )
    runs: List[TransitionRun] = []
    for entry in log:
        if not isinstance(entry, dict):
            continue
        try:
            runs.append(TransitionRun(
                id=str(entry.get("id") or ""),
                started_at=float(entry.get("startedAt") or 0.0),
                finished_at=_coerce_optional_float(entry.get("finishedAt")),
                duration_ms=_coerce_optional_float(entry.get("durationMs")),
                error=entry.get("error") if entry.get("error") else None,
                layout_shifts=float(entry.get("layoutShifts") or 0.0),
                max_shift_value=float(entry.get("maxShiftValue") or 0.0),
                groups=[str(g) for g in (entry.get("groups") or [])],
            ))
        except (TypeError, ValueError) as error:
            raise ViewTransitionsError(
                f"malformed transition entry {entry!r}: {error}"
            ) from error
    return runs


def _coerce_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------- assertions --------------------------------------------------

def assert_all_finished(runs: Sequence[TransitionRun]) -> None:
    """Assert every recorded run completed without error."""
    if not runs:
        raise ViewTransitionsError("no transitions recorded")
    failed = [r for r in runs if not r.is_finished()]
    if failed:
        joined = ", ".join(
            f"{r.id}({r.error or 'unfinished'})" for r in failed
        )
        raise ViewTransitionsError(f"transition failures: {joined}")


def assert_under_duration(
    runs: Sequence[TransitionRun],
    *,
    max_duration_ms: float,
) -> None:
    """Assert each finished run's duration is ``<= max_duration_ms``."""
    if max_duration_ms <= 0:
        raise ViewTransitionsError("max_duration_ms must be > 0")
    breaches: List[str] = []
    for r in runs:
        if r.duration_ms is None:
            continue
        if r.duration_ms > max_duration_ms:
            breaches.append(f"{r.id}: {r.duration_ms:.1f}ms")
    if breaches:
        raise ViewTransitionsError(
            f"transitions exceeded {max_duration_ms}ms: {', '.join(breaches)}"
        )


def assert_cls_under(
    runs: Sequence[TransitionRun],
    *,
    max_cls: float = 0.1,
    max_single_shift: float = 0.05,
) -> None:
    """Assert cumulative layout-shift and per-shift caps are respected."""
    if max_cls < 0 or max_single_shift < 0:
        raise ViewTransitionsError("cls thresholds must be >= 0")
    breaches: List[str] = []
    for r in runs:
        if r.layout_shifts > max_cls:
            breaches.append(f"{r.id}: cumulative {r.layout_shifts:.3f} > {max_cls}")
        if r.max_shift_value > max_single_shift:
            breaches.append(
                f"{r.id}: single shift {r.max_shift_value:.3f} > {max_single_shift}"
            )
    if breaches:
        raise ViewTransitionsError("CLS budget breached: " + "; ".join(breaches))


def assert_group_present(
    runs: Sequence[TransitionRun],
    group_name: str,
) -> None:
    """Assert at least one run animated a ``::view-transition-group(name)``."""
    if not isinstance(group_name, str) or not group_name:
        raise ViewTransitionsError("group_name must be a non-empty string")
    for r in runs:
        if group_name in r.groups:
            return
    raise ViewTransitionsError(
        f"no transition animated group {group_name!r}"
    )
