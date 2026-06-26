"""
Long Animation Frame (LoAF) API。 Chrome 在 2024 推出的新觀測 API,取代
``longtask`` —— 不只是 50ms+ task,而是包含整個 rAF + style/layout/paint
的「卡幀」週期,讓你能找出實際造成 jank 的真兇(哪個 script 跑太久、
style/layout 重算成本、forced reflow 細節)。

This module:

* Generates the JS to subscribe via ``PerformanceObserver({type:
  'long-animation-frame'})``.
* Parses the harvested log into structured records.
* Reports per-script attribution and asserts a budget.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class LongAnimationFrameError(WebRunnerException):
    """Raised on malformed log input or budget breach."""


# ---------- instrumentation -------------------------------------------

_INSTALL = """
(function() {
  if (window.__wr_loaf_installed__) return;
  window.__wr_loaf_installed__ = true;
  window.__wr_loaf_log__ = [];
  if (!('PerformanceObserver' in window)) return;
  try {
    const obs = new PerformanceObserver(function(list) {
      list.getEntries().forEach(function(e) {
        const scripts = (e.scripts || []).map(function(s) {
          return {
            name: s.name || '',
            invoker: s.invoker || '',
            invoker_type: s.invokerType || '',
            source_url: s.sourceURL || '',
            duration_ms: s.duration,
            forced_style_layout_duration_ms: s.forcedStyleAndLayoutDuration || 0,
            pause_duration_ms: s.pauseDuration || 0
          };
        });
        window.__wr_loaf_log__.push({
          duration_ms: e.duration,
          render_start_ms: e.renderStart || 0,
          style_layout_start_ms: e.styleAndLayoutStart || 0,
          start_time_ms: e.startTime,
          blocking_duration_ms: e.blockingDuration || 0,
          scripts: scripts
        });
      });
    });
    obs.observe({type: 'long-animation-frame', buffered: true});
  } catch (e) { /* unsupported */ }
})();
""".strip()


def build_install_script() -> str:
    return _INSTALL


HARVEST_SCRIPT = "return window.__wr_loaf_log__ || [];"


# ---------- data --------------------------------------------------------

@dataclass
class ScriptAttribution:
    """Per-script breakdown inside a long animation frame."""

    name: str
    invoker: str
    invoker_type: str
    source_url: str
    duration_ms: float
    forced_style_layout_duration_ms: float = 0.0
    pause_duration_ms: float = 0.0


@dataclass
class LongFrame:
    """One long-animation-frame entry."""

    start_time_ms: float
    duration_ms: float
    render_start_ms: float
    style_layout_start_ms: float
    blocking_duration_ms: float
    scripts: list[ScriptAttribution] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_log(payload: Any) -> list[LongFrame]:  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    """Convert the harvested ``__wr_loaf_log__`` array into typed frames."""
    if not isinstance(payload, list):
        raise LongAnimationFrameError(
            f"payload must be list, got {type(payload).__name__}"
        )
    out: list[LongFrame] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        try:
            scripts = []
            for sraw in raw.get("scripts") or []:
                if not isinstance(sraw, dict):
                    continue
                scripts.append(ScriptAttribution(
                    name=str(sraw.get("name") or ""),
                    invoker=str(sraw.get("invoker") or ""),
                    invoker_type=str(sraw.get("invoker_type") or ""),
                    source_url=str(sraw.get("source_url") or ""),
                    duration_ms=float(sraw.get("duration_ms") or 0.0),
                    forced_style_layout_duration_ms=float(
                        sraw.get("forced_style_layout_duration_ms") or 0.0,
                    ),
                    pause_duration_ms=float(sraw.get("pause_duration_ms") or 0.0),
                ))
            out.append(LongFrame(
                start_time_ms=float(raw.get("start_time_ms") or 0.0),
                duration_ms=float(raw.get("duration_ms") or 0.0),
                render_start_ms=float(raw.get("render_start_ms") or 0.0),
                style_layout_start_ms=float(raw.get("style_layout_start_ms") or 0.0),
                blocking_duration_ms=float(raw.get("blocking_duration_ms") or 0.0),
                scripts=scripts,
            ))
        except (TypeError, ValueError) as error:
            raise LongAnimationFrameError(
                f"malformed loaf entry {raw!r}: {error}"
            ) from error
    return out


# ---------- aggregation / reports --------------------------------------

@dataclass
class LoafReport:
    """Rolled-up view across all frames."""

    frames: list[LongFrame] = field(default_factory=list)

    def worst_frame_ms(self) -> float:
        return max((f.duration_ms for f in self.frames), default=0.0)

    def total_blocking_ms(self) -> float:
        return sum(f.blocking_duration_ms for f in self.frames)

    def top_scripts(self, *, n: int = 5) -> list[ScriptAttribution]:
        """Top N scripts by aggregated duration across all frames."""
        bucket: dict[str, ScriptAttribution] = {}
        for frame in self.frames:
            for s in frame.scripts:
                key = s.source_url or s.name or s.invoker
                existing = bucket.get(key)
                if existing is None:
                    bucket[key] = ScriptAttribution(
                        name=s.name, invoker=s.invoker,
                        invoker_type=s.invoker_type, source_url=s.source_url,
                        duration_ms=s.duration_ms,
                        forced_style_layout_duration_ms=s.forced_style_layout_duration_ms,
                        pause_duration_ms=s.pause_duration_ms,
                    )
                else:
                    existing.duration_ms += s.duration_ms
                    existing.forced_style_layout_duration_ms += (
                        s.forced_style_layout_duration_ms
                    )
                    existing.pause_duration_ms += s.pause_duration_ms
        return sorted(bucket.values(), key=lambda s: -s.duration_ms)[:n]


# ---------- assertions -------------------------------------------------

def assert_no_frame_over(report: LoafReport, *, max_ms: float) -> None:
    """Assert every frame's duration is ``<= max_ms``."""
    if not isinstance(report, LoafReport):
        raise LongAnimationFrameError("expects LoafReport")
    if max_ms <= 0:
        raise LongAnimationFrameError("max_ms must be > 0")
    bad = [f for f in report.frames if f.duration_ms > max_ms]
    if bad:
        sample = ", ".join(f"{f.duration_ms:.0f}ms" for f in bad[:3])
        more = "" if len(bad) <= 3 else f" (+{len(bad) - 3})"
        raise LongAnimationFrameError(
            f"long animation frames over {max_ms}ms: {sample}{more}"
        )


def assert_total_blocking_under(report: LoafReport, *, max_ms: float) -> None:
    """Assert total blocking time across all frames is ``<= max_ms``."""
    if not isinstance(report, LoafReport):
        raise LongAnimationFrameError("expects LoafReport")
    if max_ms < 0:
        raise LongAnimationFrameError("max_ms must be >= 0")
    total = report.total_blocking_ms()
    if total > max_ms:
        raise LongAnimationFrameError(
            f"total blocking {total:.1f}ms exceeds budget {max_ms}ms"
        )
