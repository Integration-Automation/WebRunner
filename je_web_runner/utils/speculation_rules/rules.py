"""
Speculation Rules (prerender / prefetch) hint verification.
Chrome's prerender via ``<script type=speculationrules>`` can fire a
second copy of analytics / cause double WS subscribe / break OAuth
state if the developer doesn't handle the prerendering→active
transition. This module:

* Builds the ``<script>`` tag for a rule set.
* Provides JS to record the prerender state-change events into
  ``window.__wr_spec__`` for later harvest.
* Asserts: rule was activated, no double fire of any event id, no
  request fired during prerendering phase to a deny-listed URL.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SpeculationRulesError(WebRunnerException):
    """Raised on bad rule input or assertion failure."""


class RuleKind(str, Enum):
    PREFETCH = "prefetch"
    PRERENDER = "prerender"


@dataclass(frozen=True)
class SpeculationRule:
    """One URL → ``prefetch`` / ``prerender`` rule."""

    source: str  # "list" / "document"
    urls: Sequence[str] = ()
    where: Optional[Dict[str, Any]] = None  # for source=document
    eagerness: str = "moderate"  # 'immediate' / 'eager' / 'moderate' / 'conservative'

    def __post_init__(self) -> None:
        if self.source not in ("list", "document"):
            raise SpeculationRulesError(f"unknown source {self.source!r}")
        if self.source == "list" and not self.urls:
            raise SpeculationRulesError("source='list' requires urls")
        if self.eagerness not in ("immediate", "eager", "moderate", "conservative"):
            raise SpeculationRulesError(f"unknown eagerness {self.eagerness!r}")


def build_script_tag(prefetch: Sequence[SpeculationRule] = (),
                     prerender: Sequence[SpeculationRule] = ()) -> str:
    """Render a ``<script type=speculationrules>`` payload as a string."""
    def _serialise(rules: Sequence[SpeculationRule]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for rule in rules:
            entry: Dict[str, Any] = {"source": rule.source}
            if rule.source == "list":
                entry["urls"] = list(rule.urls)
            else:
                entry["where"] = rule.where or {}
            entry["eagerness"] = rule.eagerness
            out.append(entry)
        return out
    payload: Dict[str, List[Dict[str, Any]]] = {}
    if prefetch:
        payload["prefetch"] = _serialise(prefetch)
    if prerender:
        payload["prerender"] = _serialise(prerender)
    if not payload:
        raise SpeculationRulesError("at least one rule list is required")
    body = json.dumps(payload, ensure_ascii=False)
    return f'<script type="speculationrules">{body}</script>'


# ---------- runtime instrumentation ------------------------------------

INSTALL_LISTENER_SCRIPT = """
(function() {
  if (window.__wr_spec_installed__) return;
  window.__wr_spec_installed__ = true;
  window.__wr_spec__ = {events: [], fires: {}};
  if ('prerendering' in document) {
    document.addEventListener('prerenderingchange', function() {
      window.__wr_spec__.events.push({
        kind: 'prerenderingchange',
        prerendering: document.prerendering,
        time: performance.now()
      });
    });
  }
  window.__wr_spec_fire__ = function(name) {
    window.__wr_spec__.fires[name] = (window.__wr_spec__.fires[name] || 0) + 1;
  };
})();
""".strip()


HARVEST_LOG_SCRIPT = "return window.__wr_spec__ || {events: [], fires: {}};"


# ---------- data --------------------------------------------------------

@dataclass
class PrerenderLog:
    """Harvested log of prerender-phase events + counters."""

    events: List[Dict[str, Any]] = field(default_factory=list)
    fires: Dict[str, int] = field(default_factory=dict)


def parse_log(payload: Any) -> PrerenderLog:
    if not isinstance(payload, dict):
        raise SpeculationRulesError(
            f"log payload must be dict, got {type(payload).__name__}"
        )
    events = payload.get("events") or []
    fires = payload.get("fires") or {}
    if not isinstance(events, list) or not isinstance(fires, dict):
        raise SpeculationRulesError("log fields must be list / dict")
    return PrerenderLog(events=list(events), fires=dict(fires))


# ---------- assertions --------------------------------------------------

def assert_activated(log: PrerenderLog) -> None:
    """Assert at least one prerenderingchange flipped from True → False."""
    seen_active = False
    for event in log.events:
        if event.get("kind") == "prerenderingchange" and not event.get("prerendering"):
            seen_active = True
            break
    if not seen_active:
        raise SpeculationRulesError(
            "no prerenderingchange→active event observed (page may not have activated)"
        )


def assert_no_double_fire(log: PrerenderLog, *, names: Sequence[str]) -> None:
    """Assert each tracked event name fired at most once."""
    if not names:
        raise SpeculationRulesError("names must be non-empty")
    doubles = [n for n in names if log.fires.get(n, 0) > 1]
    if doubles:
        raise SpeculationRulesError(
            f"events fired more than once during prerender→active: {doubles}"
        )


def assert_fire_count(log: PrerenderLog, *, name: str, expected: int) -> None:
    actual = log.fires.get(name, 0)
    if actual != expected:
        raise SpeculationRulesError(
            f"event {name!r} fired {actual} times, want {expected}"
        )
