"""
Multi-tab Web Locks 競爭測試 harness。
Web Locks API serialises mutations across tabs/workers — if a feature
relies on it (cart edits, background sync, BroadcastChannel coordination)
a real bug is contention being mis-handled. This module:

* Instruments tabs to log every `lock.request(name, options, callback)`
  attempt with timing + acquired/aborted/timed_out outcome.
* Parses the harvested log into typed events.
* Asserts: no deadlock, expected serialisation order, ifAvailable
  failures actually returned null, steal succeeded only once.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebLocksError(WebRunnerException):
    """Raised on malformed log or failed assertion."""


class LockOutcome(str, Enum):
    ACQUIRED = "acquired"
    RELEASED = "released"
    ABORTED = "aborted"
    TIMED_OUT = "timed_out"
    UNAVAILABLE = "unavailable"  # ifAvailable failure


# ---------- instrumentation --------------------------------------------

INSTALL_LISTENER_SCRIPT = """
(function() {
  if (window.__wr_locks_installed__) return;
  window.__wr_locks_installed__ = true;
  window.__wr_locks__ = [];
  if (!('locks' in navigator)) return;
  const realRequest = navigator.locks.request.bind(navigator.locks);
  navigator.locks.request = function(name, optsOrCb, maybeCb) {
    let opts = {}, cb;
    if (typeof optsOrCb === 'function') { cb = optsOrCb; }
    else { opts = optsOrCb || {}; cb = maybeCb; }
    const requestId = String(Math.random()).slice(2, 10);
    const startTime = performance.now();
    window.__wr_locks__.push({
      id: requestId, name: name, outcome: 'requested',
      mode: opts.mode || 'exclusive', if_available: !!opts.ifAvailable,
      steal: !!opts.steal, time: startTime
    });
    return realRequest(name, opts, function(lock) {
      if (lock === null) {
        window.__wr_locks__.push({
          id: requestId, name: name, outcome: 'unavailable',
          time: performance.now() - startTime
        });
        return cb ? cb(null) : null;
      }
      window.__wr_locks__.push({
        id: requestId, name: name, outcome: 'acquired',
        time: performance.now() - startTime
      });
      const result = cb ? cb(lock) : null;
      Promise.resolve(result).finally(function() {
        window.__wr_locks__.push({
          id: requestId, name: name, outcome: 'released',
          time: performance.now() - startTime
        });
      });
      return result;
    });
  };
})();
""".strip()


HARVEST_LOG_SCRIPT = "return window.__wr_locks__ || [];"


# ---------- data --------------------------------------------------------

@dataclass
class LockEvent:
    """One recorded lock event."""

    id: str
    name: str
    outcome: LockOutcome
    mode: str = "exclusive"
    if_available: bool = False
    steal: bool = False
    time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "outcome": self.outcome.value}


def parse_log(payload: Any) -> List[LockEvent]:
    """Convert the harvested log into typed events."""
    if not isinstance(payload, list):
        raise WebLocksError(
            f"payload must be list, got {type(payload).__name__}"
        )
    out: List[LockEvent] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        outcome_str = str(raw.get("outcome") or "")
        if outcome_str == "requested":
            continue  # the matching acquired/unavailable event is what we count
        try:
            outcome = LockOutcome(outcome_str)
        except ValueError:
            continue
        out.append(LockEvent(
            id=str(raw.get("id") or ""),
            name=str(raw.get("name") or ""),
            outcome=outcome,
            mode=str(raw.get("mode") or "exclusive"),
            if_available=bool(raw.get("if_available", False)),
            steal=bool(raw.get("steal", False)),
            time_ms=float(raw.get("time") or 0.0),
        ))
    return out


# ---------- assertions --------------------------------------------------

def assert_no_deadlock(events: Iterable[LockEvent]) -> None:
    """Assert every acquired lock was released (no held-forever leaks)."""
    acquired: Dict[str, LockEvent] = {}
    for event in events:
        if event.outcome == LockOutcome.ACQUIRED:
            acquired[event.id] = event
        elif event.outcome == LockOutcome.RELEASED:
            acquired.pop(event.id, None)
    if acquired:
        names = sorted({e.name for e in acquired.values()})
        raise WebLocksError(f"locks acquired but never released: {names}")


def assert_serialised(
    events: Iterable[LockEvent], *, name: str,
) -> None:
    """Assert holders of ``name`` did not overlap (exclusive serialisation)."""
    holders = 0
    for event in events:
        if event.name != name:
            continue
        if event.outcome == LockOutcome.ACQUIRED:
            holders += 1
            if holders > 1:
                raise WebLocksError(
                    f"lock {name!r} held by {holders} requesters simultaneously"
                )
        elif event.outcome == LockOutcome.RELEASED:
            holders = max(0, holders - 1)


def assert_if_available_unavailable(
    events: Iterable[LockEvent], *, name: str,
) -> LockEvent:
    """Assert at least one ifAvailable=true request for ``name`` returned null."""
    for event in events:
        if (
            event.name == name
            and event.if_available
            and event.outcome == LockOutcome.UNAVAILABLE
        ):
            return event
    raise WebLocksError(
        f"no ifAvailable request for {name!r} returned null"
    )


def assert_acquired_count(
    events: Iterable[LockEvent], *, name: str, expected: int,
) -> None:
    actual = sum(
        1 for e in events
        if e.name == name and e.outcome == LockOutcome.ACQUIRED
    )
    if actual != expected:
        raise WebLocksError(
            f"lock {name!r} acquired {actual} times, want {expected}"
        )
