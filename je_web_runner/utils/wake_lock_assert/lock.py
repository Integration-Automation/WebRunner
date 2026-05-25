"""
Screen Wake Lock API assertions.

Common bugs:

* Page acquires a wake lock and forgets to release it → battery drain.
* Page acquires repeatedly without releasing → handle leak.
* Page should release on visibilitychange (tab hidden) but doesn't.
* Page expects the OS-released event (`onrelease`) and never re-acquires
  when the tab becomes visible again.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WakeLockAssertError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


INSTALL_SCRIPT = r"""
(function () {
  if (window.__wr_wakelock__) return;
  const events = [];
  if (navigator.wakeLock) {
    const origRequest = navigator.wakeLock.request.bind(navigator.wakeLock);
    navigator.wakeLock.request = async function (type) {
      const sentinel = await origRequest(type || 'screen');
      events.push({kind: 'acquire', type: type || 'screen', ts: Date.now()});
      const origRelease = sentinel.release.bind(sentinel);
      sentinel.release = async function () {
        events.push({kind: 'release', type: sentinel.type, ts: Date.now(),
                     by: 'app'});
        return origRelease();
      };
      sentinel.addEventListener('release', () => {
        events.push({kind: 'release', type: sentinel.type,
                     ts: Date.now(), by: 'os'});
      });
      return sentinel;
    };
  }
  window.__wr_wakelock__ = {
    drain: function () { return events.splice(0); },
  };
})();
"""


@dataclass
class WakeLockEvent:
    kind: str        # "acquire" | "release"
    type: str = "screen"
    ts_ms: int = 0
    by: str = ""     # "app" | "os" — release events only


@dataclass
class WakeLockLog:
    events: List[WakeLockEvent] = field(default_factory=list)

    @property
    def acquired_count(self) -> int:
        return sum(1 for e in self.events if e.kind == "acquire")

    @property
    def released_count(self) -> int:
        return sum(1 for e in self.events if e.kind == "release")


def parse_log(payload: Any) -> WakeLockLog:
    if not isinstance(payload, list):
        raise WakeLockAssertError("payload must be a list")
    events: List[WakeLockEvent] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "")
        if kind not in ("acquire", "release"):
            continue
        events.append(WakeLockEvent(
            kind=kind,
            type=str(raw.get("type") or "screen"),
            ts_ms=int(raw.get("ts") or 0),
            by=str(raw.get("by") or ""),
        ))
    return WakeLockLog(events=events)


def assert_acquired(log: WakeLockLog) -> None:
    if log.acquired_count == 0:
        raise WakeLockAssertError(
            "page never called navigator.wakeLock.request()"
        )


def assert_no_leak(log: WakeLockLog) -> None:
    """Every acquire must be paired with a release (or OS auto-release)."""
    leaks = log.acquired_count - log.released_count
    if leaks > 0:
        raise WakeLockAssertError(
            f"{leaks} wake lock(s) acquired but never released — "
            "page is draining the battery"
        )


def assert_released_by_app(log: WakeLockLog) -> None:
    """For predictable lifecycle, the *app* should explicitly release —
    relying on the OS auto-release is fragile."""
    app_releases = [e for e in log.events
                    if e.kind == "release" and e.by == "app"]
    if not app_releases:
        raise WakeLockAssertError(
            "no application-driven release — page is relying on OS to release"
        )


def assert_re_acquired_after_visibility(log: WakeLockLog) -> None:
    """After an OS release (caused by tab hidden), the page should
    re-acquire when it becomes visible again."""
    has_os_release = any(e.kind == "release" and e.by == "os"
                         for e in log.events)
    if not has_os_release:
        return   # OS never released — nothing to verify
    last_os_release_idx = max(
        i for i, e in enumerate(log.events)
        if e.kind == "release" and e.by == "os"
    )
    has_later_acquire = any(
        e.kind == "acquire" for e in log.events[last_os_release_idx + 1:]
    )
    if not has_later_acquire:
        raise WakeLockAssertError(
            "OS released the wake lock but page never re-acquired — "
            "feature will be silently broken after tab toggle"
        )
