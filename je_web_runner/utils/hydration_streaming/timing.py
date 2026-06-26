"""
Streaming SSR (React 18 Suspense / Astro / Solid) per-boundary 抵達時序。
Streaming SSR sends HTML in chunks: ``<!--$?-->...<!--/$?-->`` (React),
``astro-island`` slot markers (Astro), etc. The whole-page LCP /
hydration-mismatch tests miss the case where ONE Suspense boundary is
slow / stuck.

This module instruments the page to record when each boundary marker
appears in the DOM + when its descendant becomes interactive, then
asserts per-boundary budgets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class HydrationStreamingError(WebRunnerException):
    """Raised on bad payload or budget breach."""


INSTALL_SCRIPT = """
(function() {
  if (window.__wr_hs_installed__) return;
  window.__wr_hs_installed__ = true;
  window.__wr_hs__ = {boundaries: {}, start: performance.now()};
  function note(id, phase) {
    const t = performance.now();
    if (!window.__wr_hs__.boundaries[id]) {
      window.__wr_hs__.boundaries[id] = {};
    }
    if (!(phase in window.__wr_hs__.boundaries[id])) {
      window.__wr_hs__.boundaries[id][phase] = t;
    }
  }
  // React Suspense markers (<!--$?-->, <!--$-->, <!--/$-->) sit as comment
  // nodes; observe insertion to detect arrivals.
  const obs = new MutationObserver(function(records) {
    for (const r of records) {
      for (const node of r.addedNodes || []) {
        if (node.nodeType === 8) {  // comment node
          const text = node.nodeValue || '';
          if (text.startsWith('$?')) {
            // Pending placeholder with id after marker, e.g. "$?B:1"
            note(text.slice(2).trim() || 'anon', 'placeholder');
          } else if (text.startsWith('$')) {
            note(text.slice(1).trim() || 'anon', 'arrived');
          }
        } else if (node.nodeType === 1) {
          const sel = node.getAttribute && node.getAttribute('data-suspense-id');
          if (sel) note(sel, 'arrived');
          const island = node.getAttribute && node.getAttribute('data-astro-island');
          if (island) note(island, 'arrived');
        }
      }
    }
  });
  obs.observe(document.documentElement, {childList: true, subtree: true});
  // Hydration-complete hook: app can call window.__wr_hs_done__('id')
  window.__wr_hs_done__ = function(id) { note(id, 'interactive'); };
})();
""".strip()


HARVEST_SCRIPT = "return window.__wr_hs__ || {boundaries: {}, start: 0};"


# ---------- data --------------------------------------------------------

@dataclass
class BoundaryTiming:
    """Per-Suspense / per-island timing snapshot."""

    id: str
    placeholder_ms: float | None = None
    arrived_ms: float | None = None
    interactive_ms: float | None = None

    def time_to_arrival(self) -> float | None:
        if self.placeholder_ms is None or self.arrived_ms is None:
            return None
        return self.arrived_ms - self.placeholder_ms

    def time_to_interactive(self) -> float | None:
        if self.arrived_ms is None or self.interactive_ms is None:
            return None
        return self.interactive_ms - self.arrived_ms


@dataclass
class StreamingReport:
    boundaries: list[BoundaryTiming] = field(default_factory=list)

    def by_id(self) -> dict[str, BoundaryTiming]:
        return {b.id: b for b in self.boundaries}


def parse_log(payload: Any) -> StreamingReport:
    if not isinstance(payload, dict):
        raise HydrationStreamingError(
            f"payload must be dict, got {type(payload).__name__}"
        )
    raw_boundaries = payload.get("boundaries") or {}
    if not isinstance(raw_boundaries, dict):
        raise HydrationStreamingError("boundaries must be a dict")
    out: list[BoundaryTiming] = []
    for bid, phases in raw_boundaries.items():
        if not isinstance(phases, dict):
            continue
        out.append(BoundaryTiming(
            id=str(bid),
            placeholder_ms=_to_float(phases.get("placeholder")),
            arrived_ms=_to_float(phases.get("arrived")),
            interactive_ms=_to_float(phases.get("interactive")),
        ))
    return StreamingReport(boundaries=out)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------- assertions --------------------------------------------------

def assert_all_arrived(report: StreamingReport) -> None:
    pending = [b.id for b in report.boundaries if b.arrived_ms is None]
    if pending:
        raise HydrationStreamingError(
            f"streaming boundaries never arrived: {pending}"
        )


def assert_arrival_under(
    report: StreamingReport, *, id_: str, max_ms: float,
) -> float:
    if max_ms <= 0:
        raise HydrationStreamingError("max_ms must be > 0")
    target = report.by_id().get(id_)
    if target is None:
        raise HydrationStreamingError(f"no boundary {id_!r} in report")
    delta = target.time_to_arrival()
    if delta is None:
        raise HydrationStreamingError(
            f"boundary {id_!r} missing placeholder/arrived timing"
        )
    if delta > max_ms:
        raise HydrationStreamingError(
            f"boundary {id_!r} arrival took {delta:.1f}ms (> {max_ms}ms)"
        )
    return delta


def assert_interactive_under(
    report: StreamingReport, *, id_: str, max_ms: float,
) -> float:
    if max_ms <= 0:
        raise HydrationStreamingError("max_ms must be > 0")
    target = report.by_id().get(id_)
    if target is None:
        raise HydrationStreamingError(f"no boundary {id_!r} in report")
    delta = target.time_to_interactive()
    if delta is None:
        raise HydrationStreamingError(
            f"boundary {id_!r} missing arrived/interactive timing"
        )
    if delta > max_ms:
        raise HydrationStreamingError(
            f"boundary {id_!r} hydration took {delta:.1f}ms (> {max_ms}ms)"
        )
    return delta


def assert_order(
    report: StreamingReport, *, expected_order: Sequence[str],
) -> None:
    """Assert boundaries arrived in the given order (by arrived_ms ascending)."""
    if not expected_order:
        raise HydrationStreamingError("expected_order must be non-empty")
    arrivals = [
        (b.arrived_ms, b.id)
        for b in report.boundaries
        if b.arrived_ms is not None and b.id in expected_order
    ]
    arrivals.sort()
    actual = [bid for _, bid in arrivals]
    if actual != list(expected_order):
        raise HydrationStreamingError(
            f"boundary arrival order {actual} != expected {list(expected_order)}"
        )
