"""
逐個 block 第三方 vendor,觀察主要流程是否還能跑完(availability threat
model)。E.g.「如果 Stripe.js 載入失敗,checkout 還能 graceful degrade
嗎?」「Google Analytics 慢,首屏會被擋嗎?」

Strategy: For each vendor in a catalogue (or caller-supplied list),
build a CDP block-URL pattern set, run the user's flow callable, then
classify the result as resilient / degraded / broken.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ThirdPartyBlockError(WebRunnerException):
    """Raised on bad inputs or assertion failure."""


class Resilience(str, Enum):
    RESILIENT = "resilient"
    DEGRADED = "degraded"
    BROKEN = "broken"


# ---------- vendor catalogue -------------------------------------------

@dataclass(frozen=True)
class Vendor:
    """One third-party vendor and its URL patterns to block."""

    name: str
    patterns: Sequence[str]
    critical_path: bool = False  # if True, breakage is expected (don't classify as bug)


_BUILTIN_VENDORS: Sequence[Vendor] = (
    Vendor(name="google_analytics", patterns=(
        "*://www.google-analytics.com/*", "*://www.googletagmanager.com/*",
    )),
    Vendor(name="facebook_pixel", patterns=(
        "*://connect.facebook.net/*", "*://www.facebook.com/tr/*",
    )),
    Vendor(name="hotjar", patterns=(
        "*://*.hotjar.com/*",
    )),
    Vendor(name="intercom", patterns=(
        "*://widget.intercom.io/*", "*://api.intercom.io/*",
    )),
    Vendor(name="stripe", patterns=(
        "*://js.stripe.com/*", "*://m.stripe.com/*",
    ), critical_path=True),  # blocking Stripe will break payment
    Vendor(name="segment", patterns=(
        "*://cdn.segment.com/*", "*://api.segment.io/*",
    )),
    Vendor(name="mixpanel", patterns=(
        "*://cdn.mxpnl.com/*", "*://api.mixpanel.com/*",
    )),
    Vendor(name="sentry", patterns=(
        "*://*.sentry.io/*",
    )),
    Vendor(name="datadog", patterns=(
        "*://*.datadoghq.com/*", "*://*.datadoghq.eu/*",
    )),
)


def builtin_vendors() -> List[Vendor]:
    return list(_BUILTIN_VENDORS)


# ---------- runner ------------------------------------------------------

@dataclass
class BlockOutcome:
    """One vendor's blocked-run outcome."""

    vendor: str
    resilience: Resilience
    error: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "resilience": self.resilience.value}


@dataclass
class BlockReport:
    outcomes: List[BlockOutcome] = field(default_factory=list)

    def broken(self) -> List[BlockOutcome]:
        """Non-critical vendors that broke the flow."""
        return [o for o in self.outcomes if o.resilience == Resilience.BROKEN]

    def by_vendor(self) -> Dict[str, BlockOutcome]:
        return {o.vendor: o for o in self.outcomes}


CdpBlockApply = Callable[[Sequence[str]], None]
"""Callable: hand off block patterns to ``Network.setBlockedURLs``."""


def run_block_matrix(
    vendors: Sequence[Vendor],
    cdp_block: CdpBlockApply,
    flow: Callable[[], Optional[str]],
) -> BlockReport:
    """
    For each vendor: install block, run ``flow()``, record outcome.

    ``flow()`` returns one of:

    * ``None`` (clean pass) → ``RESILIENT``
    * a non-empty string ("degraded: payment slow") → ``DEGRADED``

    Or raises an exception → ``BROKEN``.

    The caller can mark `critical_path=True` on a vendor so a break is
    expected (still recorded but not flagged as a regression).
    """
    if not vendors:
        raise ThirdPartyBlockError("vendors must be non-empty")
    if not callable(cdp_block) or not callable(flow):
        raise ThirdPartyBlockError("cdp_block and flow must be callable")
    report = BlockReport()
    for vendor in vendors:
        try:
            cdp_block(list(vendor.patterns))
        except Exception as error:
            raise ThirdPartyBlockError(
                f"cdp_block failed for {vendor.name!r}: {error!r}"
            ) from error
        outcome = _execute_flow(vendor, flow)
        report.outcomes.append(outcome)
    # restore (unblock all)
    try:
        cdp_block([])
    except Exception:  # nosec B110 — best-effort restore
        pass
    return report


def _execute_flow(vendor: Vendor, flow: Callable[[], Optional[str]]) -> BlockOutcome:
    try:
        message = flow()
    except Exception as error:
        return BlockOutcome(
            vendor=vendor.name,
            resilience=Resilience.BROKEN,
            error=repr(error),
            notes=["critical_path vendor" if vendor.critical_path else "regression"],
        )
    if not message:
        return BlockOutcome(vendor=vendor.name, resilience=Resilience.RESILIENT)
    return BlockOutcome(
        vendor=vendor.name,
        resilience=Resilience.DEGRADED,
        notes=[str(message)],
    )


def assert_resilient_to(
    report: BlockReport, *, vendors: Sequence[str],
) -> None:
    """Assert listed vendors did not break the flow."""
    bad = [
        v for v in vendors
        if (report.by_vendor().get(v) or BlockOutcome(vendor=v, resilience=Resilience.BROKEN)).resilience == Resilience.BROKEN
    ]
    if bad:
        raise ThirdPartyBlockError(
            f"flow broke when these vendors were blocked: {bad}"
        )
