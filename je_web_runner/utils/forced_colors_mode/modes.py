"""
High-contrast / dark-mode / reduced-motion / forced-colors 矩陣驗證。
The four CSS media queries that most app teams forget:

* ``prefers-color-scheme: dark``
* ``prefers-reduced-motion: reduce``
* ``forced-colors: active`` (Windows High Contrast)
* ``prefers-contrast: more``

This module:

1. Builds the CDP ``Emulation.setEmulatedMedia`` payload for any combo.
2. Defines a default matrix of "important" combos plus a knob for
   restricting it (e.g. CI does dark-mode only).
3. Diffs visible CSS properties (computed background / color / outline)
   between modes to catch "white-on-white text in high-contrast" bugs.

CDP application is delegated to a user-supplied callable so the module
stays driver-agnostic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ForcedColorsModeError(WebRunnerException):
    """Raised on invalid mode combo, bad CSS payload, or CDP failure."""


class ColorScheme(str, Enum):
    LIGHT = "light"
    DARK = "dark"


class ReducedMotion(str, Enum):
    NO_PREFERENCE = "no-preference"
    REDUCE = "reduce"


class ForcedColors(str, Enum):
    NONE = "none"
    ACTIVE = "active"


class Contrast(str, Enum):
    NO_PREFERENCE = "no-preference"
    MORE = "more"
    LESS = "less"


# ---------- profile model ----------------------------------------------

@dataclass(frozen=True)
class MediaProfile:
    """One full CSS-media combo."""

    name: str
    color_scheme: ColorScheme = ColorScheme.LIGHT
    reduced_motion: ReducedMotion = ReducedMotion.NO_PREFERENCE
    forced_colors: ForcedColors = ForcedColors.NONE
    contrast: Contrast = Contrast.NO_PREFERENCE

    def to_cdp_features(self) -> List[Dict[str, str]]:
        """Render the ``features`` payload for ``Emulation.setEmulatedMedia``."""
        return [
            {"name": "prefers-color-scheme", "value": self.color_scheme.value},
            {"name": "prefers-reduced-motion", "value": self.reduced_motion.value},
            {"name": "forced-colors", "value": self.forced_colors.value},
            {"name": "prefers-contrast", "value": self.contrast.value},
        ]


DEFAULT_PROFILES: Sequence[MediaProfile] = (
    MediaProfile(name="baseline"),
    MediaProfile(name="dark", color_scheme=ColorScheme.DARK),
    MediaProfile(name="reduced-motion", reduced_motion=ReducedMotion.REDUCE),
    MediaProfile(name="high-contrast",
                 forced_colors=ForcedColors.ACTIVE,
                 contrast=Contrast.MORE),
    MediaProfile(name="dark-high-contrast",
                 color_scheme=ColorScheme.DARK,
                 forced_colors=ForcedColors.ACTIVE,
                 contrast=Contrast.MORE),
)


# ---------- CDP integration --------------------------------------------

CdpEmulate = Callable[[List[Dict[str, str]]], Any]
"""Callable that pushes a features list to ``Emulation.setEmulatedMedia``."""


def apply_profile(profile: MediaProfile, cdp_emulate: CdpEmulate) -> Any:
    """Hand the profile's features to the user's CDP-emulate callable."""
    if not isinstance(profile, MediaProfile):
        raise ForcedColorsModeError("apply_profile expects MediaProfile")
    try:
        return cdp_emulate(profile.to_cdp_features())
    except Exception as error:
        raise ForcedColorsModeError(
            f"CDP setEmulatedMedia failed: {error!r}"
        ) from error


# ---------- per-element style snapshot ---------------------------------

@dataclass(frozen=True)
class StyleSnapshot:
    """Subset of computed styles we compare across modes."""

    background_color: str
    color: str
    outline: str = ""
    border_color: str = ""
    visibility: str = "visible"

    def is_invisible(self) -> bool:
        """Heuristic: same colour as background = invisible."""
        return (
            self.background_color.strip().lower() == self.color.strip().lower()
            and self.background_color.strip() != ""
        )


@dataclass
class ElementDiff:
    """Difference for one element between two modes."""

    selector: str
    baseline_mode: str
    other_mode: str
    became_invisible: bool
    changed_fields: Dict[str, Any] = field(default_factory=dict)


def diff_snapshot(
    selector: str,
    baseline_mode: str,
    other_mode: str,
    baseline: StyleSnapshot,
    other: StyleSnapshot,
) -> Optional[ElementDiff]:
    """Return a :class:`ElementDiff` iff the snapshots meaningfully differ."""
    if not isinstance(baseline, StyleSnapshot) or not isinstance(other, StyleSnapshot):
        raise ForcedColorsModeError("snapshots must be StyleSnapshot instances")
    changed: Dict[str, Any] = {}
    for field_name in asdict(baseline):
        a = getattr(baseline, field_name)
        b = getattr(other, field_name)
        if a != b:
            changed[field_name] = {"baseline": a, "other": b}
    became_invisible = other.is_invisible() and not baseline.is_invisible()
    if not changed and not became_invisible:
        return None
    return ElementDiff(
        selector=selector,
        baseline_mode=baseline_mode,
        other_mode=other_mode,
        became_invisible=became_invisible,
        changed_fields=changed,
    )


# ---------- matrix audit ------------------------------------------------

@dataclass
class ModeAuditReport:
    """Roll-up returned by :func:`audit_modes`."""

    diffs: List[ElementDiff] = field(default_factory=list)
    invisible_in_modes: Dict[str, List[str]] = field(default_factory=dict)

    def passed(self) -> bool:
        return not self.invisible_in_modes


def audit_modes(
    baseline_mode: str,
    snapshots_by_mode: Dict[str, Dict[str, StyleSnapshot]],
) -> ModeAuditReport:
    """
    Given per-mode { selector → StyleSnapshot }, diff every non-baseline
    mode against the baseline. Selectors that become invisible are
    flagged as failures; other diffs are recorded for review.
    """
    if baseline_mode not in snapshots_by_mode:
        raise ForcedColorsModeError(
            f"baseline_mode {baseline_mode!r} not in snapshots_by_mode"
        )
    baseline = snapshots_by_mode[baseline_mode]
    report = ModeAuditReport()
    for mode, snapshots in snapshots_by_mode.items():
        if mode == baseline_mode:
            continue
        for selector, snap in snapshots.items():
            if selector not in baseline:
                continue
            diff = diff_snapshot(
                selector, baseline_mode, mode, baseline[selector], snap,
            )
            if diff is None:
                continue
            report.diffs.append(diff)
            if diff.became_invisible:
                report.invisible_in_modes.setdefault(mode, []).append(selector)
    return report


def assert_no_invisible(report: ModeAuditReport) -> None:
    """Raise if any element became invisible in any non-baseline mode."""
    if not isinstance(report, ModeAuditReport):
        raise ForcedColorsModeError("assert_no_invisible expects ModeAuditReport")
    if report.passed():
        return
    parts = ", ".join(
        f"{mode}: {len(selectors)} element(s)"
        for mode, selectors in report.invisible_in_modes.items()
    )
    raise ForcedColorsModeError(f"elements became invisible — {parts}")
