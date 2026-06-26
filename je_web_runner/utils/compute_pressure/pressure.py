"""
Compute Pressure API simulation + app-throttle reaction assertions.

The Compute Pressure API tells web apps "the CPU is under stress —
please throttle your background work". This module:

* Installs a fake ``PressureObserver`` whose ``observe()`` callback the
  test driver can fire with synthetic pressure samples
  (``nominal``/``fair``/``serious``/``critical``).
* Records every reaction the app makes (the page-side helper
  ``__wr_cp__.recordReaction(name)`` is exposed for app code to call
  when it throttles).
* Provides assertions: at least one reaction at critical pressure, no
  CPU-heavy work at serious+, no observer leaks (close called).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ComputePressureError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


class PressureLevel(str, Enum):
    NOMINAL = "nominal"
    FAIR = "fair"
    SERIOUS = "serious"
    CRITICAL = "critical"


_ORDER = {
    PressureLevel.NOMINAL: 0,
    PressureLevel.FAIR: 1,
    PressureLevel.SERIOUS: 2,
    PressureLevel.CRITICAL: 3,
}


INSTALL_SCRIPT = r"""
(function () {
  if (window.__wr_cp__) return;
  let observerCallback = null;
  let observerActive = false;
  const reactions = [];
  const closed = [];
  function FakePressureObserver(cb) {
    observerCallback = cb;
  }
  FakePressureObserver.prototype.observe = async function (source) {
    observerActive = true;
  };
  FakePressureObserver.prototype.disconnect = function () {
    observerActive = false;
    closed.push({ts: Date.now()});
  };
  window.PressureObserver = FakePressureObserver;
  window.__wr_cp__ = {
    fire: function (level) {
      if (!observerCallback) return false;
      observerCallback([{state: level, source: 'cpu', time: Date.now()}],
                       {state: level});
      return true;
    },
    recordReaction: function (name) {
      reactions.push({name: String(name || ''), ts: Date.now()});
    },
    drainReactions: function () { return reactions.splice(0); },
    drainClosed: function () { return closed.splice(0); },
    active: function () { return observerActive; },
  };
})();
"""


@dataclass
class PressureReaction:
    name: str
    level: PressureLevel = PressureLevel.NOMINAL
    ts_ms: int = 0


@dataclass
class PressureLog:
    reactions: list[PressureReaction] = field(default_factory=list)
    disconnect_count: int = 0
    fires: list[PressureLevel] = field(default_factory=list)


def parse_log(payload: Any) -> PressureLog:
    if not isinstance(payload, dict):
        raise ComputePressureError("payload must be a dict")
    reactions: list[PressureReaction] = []
    for raw in payload.get("reactions") or []:
        if not isinstance(raw, dict):
            continue
        try:
            level = PressureLevel(raw.get("level", PressureLevel.NOMINAL.value))
        except ValueError as exc:
            raise ComputePressureError(
                f"unknown pressure level {raw.get('level')!r}"
            ) from exc
        reactions.append(PressureReaction(
            name=str(raw.get("name") or ""),
            level=level,
            ts_ms=int(raw.get("ts") or 0),
        ))
    fires: list[PressureLevel] = []
    for raw in payload.get("fires") or []:
        try:
            fires.append(PressureLevel(raw))
        except ValueError as exc:
            raise ComputePressureError(
                f"unknown fire level {raw!r}"
            ) from exc
    return PressureLog(
        reactions=reactions,
        disconnect_count=int(payload.get("disconnectCount") or 0),
        fires=fires,
    )


def assert_reaction_to(
    log: PressureLog, *, level: PressureLevel, name: str | None = None,
) -> PressureReaction:
    if not isinstance(level, PressureLevel):
        raise ComputePressureError("level must be PressureLevel enum")
    matches = [r for r in log.reactions
               if _ORDER[r.level] >= _ORDER[level]
               and (name is None or r.name == name)]
    if not matches:
        raise ComputePressureError(
            f"no reaction at pressure >= {level.value}"
            + (f" with name={name!r}" if name else "")
        )
    return matches[0]


def assert_throttled_at_or_above(
    log: PressureLog, *, level: PressureLevel,
) -> None:
    """If the harness fired ``serious``/``critical``, the app *must* have
    recorded at least one reaction at that or higher level."""
    fired_high = any(_ORDER[f] >= _ORDER[level] for f in log.fires)
    if not fired_high:
        return   # no high-pressure firing → nothing to verify
    high_reactions = [r for r in log.reactions
                      if _ORDER[r.level] >= _ORDER[level]]
    if not high_reactions:
        raise ComputePressureError(
            f"harness fired {level.value}+ pressure but app never throttled "
            f"({len(log.reactions)} total reactions, none >= {level.value})"
        )


def assert_observer_disconnected(log: PressureLog) -> None:
    if log.disconnect_count == 0:
        raise ComputePressureError(
            "PressureObserver never disconnected — page leaks the observer"
        )
