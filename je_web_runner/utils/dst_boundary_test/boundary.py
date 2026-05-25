"""
DST (Daylight Saving Time) boundary test harness.

Catches the classic bugs that only surface on a "spring forward" /
"fall back" weekend:

* Job-scheduler firing twice on the same wall-clock minute.
* Job missed entirely because 02:30 didn't exist that day.
* Booking UI claims "1 hour from now" but the time-zone-aware target is
  actually 2 hours away.
* Cron expression assumed UTC but executed in local zone.

The module is pure-stdlib (``zoneinfo``) — no ``pytz`` dependency.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from zoneinfo import ZoneInfo
except ImportError as exc:  # pragma: no cover — Py3.9+ has zoneinfo
    raise ImportError(
        "dst_boundary_test requires Python 3.9+ for zoneinfo"
    ) from exc

from je_web_runner.utils.exception.exceptions import WebRunnerException


class DstBoundaryError(WebRunnerException):
    """Raised when DST boundary invariants are violated."""


class Transition(str, Enum):
    SPRING_FORWARD = "spring_forward"   # gap — local time skips ahead
    FALL_BACK = "fall_back"             # overlap — local time repeats


@dataclass
class DstBoundary:
    moment_utc: datetime
    transition: Transition
    offset_before: timedelta
    offset_after: timedelta
    tz_name: str = "UTC"

    @property
    def shift(self) -> timedelta:
        return self.offset_after - self.offset_before


def find_boundaries(
    tz_name: str, start_year: int, end_year: int,
) -> List[DstBoundary]:
    """Walk ``[start_year, end_year]`` and detect every offset change."""
    if not isinstance(tz_name, str) or not tz_name:
        raise DstBoundaryError("tz_name must be non-empty string")
    if start_year > end_year:
        raise DstBoundaryError("start_year must be <= end_year")
    if end_year - start_year > 10:
        raise DstBoundaryError("range too large (>10 years)")
    try:
        tz = ZoneInfo(tz_name)
    except Exception as error:
        raise DstBoundaryError(f"unknown timezone: {tz_name!r}") from error

    boundaries: List[DstBoundary] = []
    cursor = datetime(start_year, 1, 1, tzinfo=tz)
    end = datetime(end_year, 12, 31, 23, 59, tzinfo=tz)
    step = timedelta(hours=1)
    prev_offset = cursor.utcoffset()
    while cursor <= end:
        cursor += step
        cur_offset = cursor.utcoffset()
        if cur_offset != prev_offset and prev_offset is not None and cur_offset is not None:
            delta = cur_offset - prev_offset
            transition = (Transition.SPRING_FORWARD if delta > timedelta(0)
                          else Transition.FALL_BACK)
            boundaries.append(DstBoundary(
                moment_utc=cursor.astimezone(ZoneInfo("UTC")),
                transition=transition,
                offset_before=prev_offset,
                offset_after=cur_offset,
                tz_name=tz_name,
            ))
        prev_offset = cur_offset
    return boundaries


def is_nonexistent_local_time(
    tz_name: str, wall_clock: datetime,
) -> bool:
    """True if the given naive datetime falls in a spring-forward gap."""
    if wall_clock.tzinfo is not None:
        raise DstBoundaryError(
            "wall_clock must be a naive datetime (no tzinfo)"
        )
    tz = ZoneInfo(tz_name)
    localized = wall_clock.replace(tzinfo=tz)
    # round-trip through UTC; if naive minute disappears, the resulting
    # local time will differ from the input.
    round_tripped = localized.astimezone(ZoneInfo("UTC")).astimezone(tz)
    return round_tripped.replace(tzinfo=None) != wall_clock


def is_ambiguous_local_time(tz_name: str, wall_clock: datetime) -> bool:
    """True if the given naive datetime falls in a fall-back overlap."""
    if wall_clock.tzinfo is not None:
        raise DstBoundaryError(
            "wall_clock must be a naive datetime (no tzinfo)"
        )
    tz = ZoneInfo(tz_name)
    earlier = wall_clock.replace(tzinfo=tz, fold=0)
    later = wall_clock.replace(tzinfo=tz, fold=1)
    return earlier.utcoffset() != later.utcoffset()


@dataclass
class ScheduledFire:
    moment_utc: datetime
    local_label: str


def expected_fires_around_boundary(
    boundary: DstBoundary, wall_clock_hour: int = 2, wall_clock_minute: int = 30,
) -> List[ScheduledFire]:
    """For a "daily 02:30 local" job, return what should fire on this date."""
    if not 0 <= wall_clock_hour <= 23 or not 0 <= wall_clock_minute <= 59:
        raise DstBoundaryError("wall_clock_hour/minute out of range")
    tz = ZoneInfo(boundary.tz_name)
    moment_local = boundary.moment_utc.astimezone(tz)
    day = moment_local.date()
    naive = datetime(day.year, day.month, day.day,
                     wall_clock_hour, wall_clock_minute)
    if boundary.transition == Transition.SPRING_FORWARD:
        # If the wall-clock minute disappears, no fire that day.
        return []
    # Fall back: the same wall-clock minute happens twice.
    return [
        ScheduledFire(moment_utc=naive.replace(tzinfo=tz, fold=0)
                      .astimezone(ZoneInfo("UTC")),
                      local_label=f"{naive.isoformat()} (fold=0)"),
        ScheduledFire(moment_utc=naive.replace(tzinfo=tz, fold=1)
                      .astimezone(ZoneInfo("UTC")),
                      local_label=f"{naive.isoformat()} (fold=1)"),
    ]


def assert_no_duplicate_fires(fires: Sequence[datetime]) -> None:
    """Reject schedule output that fires twice on the same UTC instant."""
    seen = set()
    for f in fires:
        if not isinstance(f, datetime) or f.tzinfo is None:
            raise DstBoundaryError("fires must be tz-aware datetimes")
        key = f.astimezone(ZoneInfo("UTC"))
        if key in seen:
            raise DstBoundaryError(
                f"duplicate fire at {key.isoformat()}"
            )
        seen.add(key)


def assert_fired_around(
    fires: Sequence[datetime],
    expected_utc: datetime,
    tolerance: timedelta = timedelta(minutes=1),
) -> None:
    """At least one fire must be within ``tolerance`` of expected."""
    if expected_utc.tzinfo is None:
        raise DstBoundaryError("expected_utc must be tz-aware")
    for f in fires:
        if abs(f.astimezone(ZoneInfo("UTC")) - expected_utc) <= tolerance:
            return
    raise DstBoundaryError(
        f"no fire within {tolerance} of {expected_utc.isoformat()}"
    )
