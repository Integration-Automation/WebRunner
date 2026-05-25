"""
Background Sync API assertions.

Catches the two big bugs offline-first apps hit:

* Tag registered but Service Worker never receives the ``sync`` event
  (typo / wrong scope).
* Sync fires once, fails, and never retries — silently losing the user's
  queued action.

The shim records each ``registration.sync.register(tag)``,
``getTags()``, and each ``sync`` event the SW dispatches. Python helpers
assert tag presence, fire count, and a retry happened at least once
when the first attempt failed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

from je_web_runner.utils.exception.exceptions import WebRunnerException


class BackgroundSyncAssertError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


INSTALL_SCRIPT = r"""
(function () {
  if (window.__wr_bg_sync__) return;
  const registered = [];
  const fired = [];
  if (navigator.serviceWorker) {
    navigator.serviceWorker.ready.then((reg) => {
      if (reg.sync) {
        const origReg = reg.sync.register.bind(reg.sync);
        reg.sync.register = function (tag) {
          registered.push(tag);
          return origReg(tag);
        };
      }
      reg.addEventListener && reg.addEventListener('sync', (e) => {
        fired.push({tag: e.tag, lastChance: !!e.lastChance, ts: Date.now()});
      });
    });
  }
  window.__wr_bg_sync__ = {
    drainRegistered: function () { return registered.splice(0); },
    drainFired: function () { return fired.splice(0); },
  };
})();
"""


@dataclass
class SyncFire:
    tag: str
    last_chance: bool = False
    ts_ms: int = 0


@dataclass
class SyncLog:
    registered: List[str] = field(default_factory=list)
    fired: List[SyncFire] = field(default_factory=list)


def parse_log(payload: Any) -> SyncLog:
    if not isinstance(payload, dict):
        raise BackgroundSyncAssertError("payload must be a dict")
    registered = list(payload.get("registered") or [])
    if not all(isinstance(r, str) for r in registered):
        raise BackgroundSyncAssertError(
            "registered list must contain strings only"
        )
    fired: List[SyncFire] = []
    for raw in payload.get("fired") or []:
        if not isinstance(raw, dict):
            continue
        fired.append(SyncFire(
            tag=str(raw.get("tag") or ""),
            last_chance=bool(raw.get("lastChance")),
            ts_ms=int(raw.get("ts") or 0),
        ))
    return SyncLog(registered=registered, fired=fired)


def assert_registered(log: SyncLog, *, tag: str) -> None:
    if not tag:
        raise BackgroundSyncAssertError("tag must be non-empty")
    if tag not in log.registered:
        raise BackgroundSyncAssertError(
            f"sync tag {tag!r} never registered; got {log.registered}"
        )


def assert_fired(log: SyncLog, *, tag: str, at_least: int = 1) -> None:
    if at_least < 1:
        raise BackgroundSyncAssertError("at_least must be >= 1")
    count = sum(1 for f in log.fired if f.tag == tag)
    if count < at_least:
        raise BackgroundSyncAssertError(
            f"sync event {tag!r} fired {count} times, expected >= {at_least}"
        )


def assert_retry_happened(log: SyncLog, *, tag: str) -> None:
    """Verify the SW got more than one ``sync`` event for ``tag`` — that's
    Chrome's retry behaviour after a failed attempt."""
    fires = [f for f in log.fired if f.tag == tag]
    if len(fires) < 2:
        raise BackgroundSyncAssertError(
            f"sync {tag!r} only fired {len(fires)} time(s) — "
            "no retry observed after failure"
        )


def assert_no_quota_exhaustion(log: SyncLog, *, tag: str) -> None:
    """Chrome marks the *last* retry attempt with ``lastChance=true``.
    Receiving that on the wire means quota is about to run out."""
    for f in log.fired:
        if f.tag == tag and f.last_chance:
            raise BackgroundSyncAssertError(
                f"sync {tag!r} reached lastChance — Chrome will drop it next"
            )
