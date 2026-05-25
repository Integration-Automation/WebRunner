"""
Pull-to-refresh / overscroll-behavior assertions for PWAs.

PWAs often re-implement pull-to-refresh themselves and forget to set
``overscroll-behavior-y: contain`` on the scroll container — leading
to *two* refresh indicators (the browser's and the app's) firing on the
same swipe.

This module records:

* Whether the page applied ``overscroll-behavior-y: contain`` to the
  scroller.
* Whether a custom refresh handler fired and whether the network
  actually re-fetched.
* Whether refresh threshold matches a sensible UX value (60–120px).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PullToRefreshError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


HARVEST_SCRIPT = r"""
(function (scrollerSelector) {
  const el = document.querySelector(scrollerSelector) || document.scrollingElement;
  const cs = getComputedStyle(el);
  return {
    overscroll_y: cs.overscrollBehaviorY || cs.overscrollBehavior,
    scroller_height: el.clientHeight,
    pull_threshold_attr: el.dataset ? el.dataset.pullThreshold || '' : '',
  };
})(arguments[0]);
"""


@dataclass
class PullToRefreshSnapshot:
    overscroll_y: str = "auto"
    scroller_height: float = 0
    pull_threshold_px: float = 0


def parse_snapshot(payload: Any) -> PullToRefreshSnapshot:
    if not isinstance(payload, dict):
        raise PullToRefreshError("payload must be a dict")
    raw_threshold = payload.get("pull_threshold_attr") or ""
    try:
        threshold = float(raw_threshold) if raw_threshold else 0
    except ValueError as exc:
        raise PullToRefreshError(
            f"pull_threshold_attr must be numeric, got {raw_threshold!r}"
        ) from exc
    return PullToRefreshSnapshot(
        overscroll_y=str(payload.get("overscroll_y") or "auto"),
        scroller_height=float(payload.get("scroller_height") or 0),
        pull_threshold_px=threshold,
    )


def assert_overscroll_contained(snap: PullToRefreshSnapshot) -> None:
    """``overscroll-behavior-y`` must NOT be ``auto`` if the page has a
    custom refresh handler — otherwise the browser also reloads."""
    if snap.overscroll_y == "auto":
        raise PullToRefreshError(
            "scroller has overscroll-behavior-y:auto — browser will trigger "
            "its own pull-to-refresh alongside the page's handler"
        )


def assert_threshold_sensible(
    snap: PullToRefreshSnapshot, *, min_px: float = 60, max_px: float = 160,
) -> None:
    if min_px <= 0 or max_px <= min_px:
        raise PullToRefreshError("min_px>0 and max_px>min_px required")
    if not snap.pull_threshold_px:
        raise PullToRefreshError(
            "scroller has no data-pull-threshold attribute"
        )
    if not min_px <= snap.pull_threshold_px <= max_px:
        raise PullToRefreshError(
            f"pull threshold {snap.pull_threshold_px}px outside "
            f"[{min_px}, {max_px}] UX band"
        )


@dataclass
class RefreshEvent:
    fired: bool = False
    network_refetched: bool = False


def assert_refresh_triggered(event: RefreshEvent) -> None:
    if not event.fired:
        raise PullToRefreshError(
            "pull gesture did not trigger the refresh handler"
        )
    if not event.network_refetched:
        raise PullToRefreshError(
            "refresh handler fired but no network refetch happened"
        )
