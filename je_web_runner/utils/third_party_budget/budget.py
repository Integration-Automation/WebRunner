"""
第三方腳本數量 / 重量 / 阻塞時間預算。
不同於 ``bundle_budget``(自家 bundle),這個只看 *第三方* 來源 —— GA、
GTM、Facebook Pixel、Hotjar、Intercom、Stripe、Cloudflare RUM…… 它們是
網站效能殺手榜冠軍,而且通常 PM 加 marketing tag 不會問 dev。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Union
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ThirdPartyBudgetError(WebRunnerException):
    """Raised on bad HAR / budget input or breach."""


# A non-exhaustive catalogue of well-known third-party hosts. Caller can
# extend via ``extra_vendors=``.
_VENDOR_CATALOGUE = {
    "google_analytics": ("www.google-analytics.com", "ssl.google-analytics.com",
                         "www.googletagmanager.com", "google-analytics.com"),
    "facebook_pixel": ("connect.facebook.net", "www.facebook.com",
                       "graph.facebook.com"),
    "hotjar": ("static.hotjar.com", "script.hotjar.com", "vars.hotjar.com",
               "in.hotjar.com"),
    "intercom": ("widget.intercom.io", "js.intercomcdn.com", "api.intercom.io"),
    "stripe": ("js.stripe.com", "m.stripe.com", "checkout.stripe.com"),
    "segment": ("cdn.segment.com", "api.segment.io"),
    "mixpanel": ("cdn.mxpnl.com", "api.mixpanel.com"),
    "amplitude": ("cdn.amplitude.com", "api.amplitude.com"),
    "linkedin": ("snap.licdn.com", "px.ads.linkedin.com"),
    "twitter": ("static.ads-twitter.com", "platform.twitter.com",
                "analytics.twitter.com"),
    "pinterest": ("s.pinimg.com", "ct.pinterest.com"),
    "datadog": ("browser-intake-datadoghq.com",),
    "sentry": ("browser.sentry-cdn.com", "ingest.sentry.io"),
    "fullstory": ("rs.fullstory.com", "edge.fullstory.com"),
    "cloudflare": ("static.cloudflareinsights.com",),
    "gtm": ("www.googletagmanager.com",),
}


# ---------- model ------------------------------------------------------

@dataclass
class ThirdPartyRequest:
    """One request classified as third-party."""

    url: str
    vendor: str
    hostname: str
    bytes_transferred: int
    duration_ms: float
    blocking: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _classify_vendor(
    hostname: str,
    extra_vendors: Dict[str, Sequence[str]],
) -> Optional[str]:
    hostname = hostname.lower()
    for vendor, hosts in {**_VENDOR_CATALOGUE, **extra_vendors}.items():
        for h in hosts:
            if hostname == h or hostname.endswith("." + h):
                return vendor
    return None


def classify_har(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    har: Union[str, Dict[str, Any]],
    *,
    first_party_hostname: str,
    extra_vendors: Optional[Dict[str, Sequence[str]]] = None,
) -> List[ThirdPartyRequest]:
    """Return one :class:`ThirdPartyRequest` per non-first-party HAR entry."""
    if not isinstance(first_party_hostname, str) or not first_party_hostname:
        raise ThirdPartyBudgetError("first_party_hostname must be non-empty")
    har_obj = _coerce_har(har)
    entries = ((har_obj.get("log") or {}).get("entries")) or []
    if not isinstance(entries, list):
        raise ThirdPartyBudgetError("har log.entries must be a list")
    extra = extra_vendors or {}
    first = first_party_hostname.lower()
    out: List[ThirdPartyRequest] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = ((entry.get("request") or {}).get("url")) or ""
        if not url:
            continue
        hostname = (urlparse(url).hostname or "").lower()
        if not hostname or _is_first_party(hostname, first):
            continue
        vendor = _classify_vendor(hostname, extra) or "unknown_third_party"
        response = entry.get("response") or {}
        size = max(
            int(response.get("_transferSize") or 0),
            int((response.get("content") or {}).get("size") or 0),
        )
        timings = entry.get("timings") or {}
        duration = 0.0
        for key in ("blocked", "dns", "connect", "send", "wait", "receive"):
            v = timings.get(key)
            if isinstance(v, (int, float)) and v > 0:
                duration += float(v)
        resource_type = str(
            entry.get("_resourceType") or entry.get("resourceType") or "",
        ).lower()
        blocking = resource_type in ("script", "stylesheet")
        out.append(ThirdPartyRequest(
            url=url, vendor=vendor, hostname=hostname,
            bytes_transferred=size, duration_ms=duration,
            blocking=blocking,
        ))
    return out


def _is_first_party(hostname: str, first_party: str) -> bool:
    return hostname == first_party or hostname.endswith("." + first_party)


def _coerce_har(har: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(har, str):
        try:
            parsed = json.loads(har)
        except ValueError as error:
            raise ThirdPartyBudgetError(f"har not JSON: {error}") from error
        if not isinstance(parsed, dict):
            raise ThirdPartyBudgetError("har JSON must be an object")
        return parsed
    if isinstance(har, dict):
        return har
    raise ThirdPartyBudgetError(
        f"classify_har expects str/dict, got {type(har).__name__}"
    )


# ---------- budgets ----------------------------------------------------

@dataclass(frozen=True)
class ThirdPartyBudget:
    """Caps for third-party traffic."""

    max_requests: Optional[int] = None
    max_bytes: Optional[int] = None
    max_blocking_ms: Optional[float] = None
    max_vendors: Optional[int] = None

    def __post_init__(self) -> None:
        for name in ("max_requests", "max_bytes", "max_blocking_ms", "max_vendors"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ThirdPartyBudgetError(f"{name} must be >= 0 if set")


@dataclass
class ThirdPartyReport:
    """Roll-up returned by :func:`evaluate`."""

    total_requests: int = 0
    total_bytes: int = 0
    blocking_ms: float = 0.0
    by_vendor: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    breaches: List[str] = field(default_factory=list)

    def passed(self) -> bool:
        return not self.breaches


def evaluate(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    requests: Sequence[ThirdPartyRequest],
    budget: ThirdPartyBudget,
) -> ThirdPartyReport:
    """Aggregate requests, compare against budget, return :class:`ThirdPartyReport`."""
    if not isinstance(budget, ThirdPartyBudget):
        raise ThirdPartyBudgetError("budget must be ThirdPartyBudget")
    report = ThirdPartyReport()
    vendors: Set[str] = set()
    for r in requests:
        if not isinstance(r, ThirdPartyRequest):
            raise ThirdPartyBudgetError(
                f"requests entry must be ThirdPartyRequest, got {type(r).__name__}"
            )
        report.total_requests += 1
        report.total_bytes += r.bytes_transferred
        if r.blocking:
            report.blocking_ms += r.duration_ms
        bucket = report.by_vendor.setdefault(r.vendor, {
            "requests": 0, "bytes": 0, "blocking_ms": 0.0,
        })
        bucket["requests"] += 1
        bucket["bytes"] += r.bytes_transferred
        if r.blocking:
            bucket["blocking_ms"] += r.duration_ms
        vendors.add(r.vendor)
    if budget.max_requests is not None and report.total_requests > budget.max_requests:
        report.breaches.append(
            f"requests {report.total_requests} > {budget.max_requests}"
        )
    if budget.max_bytes is not None and report.total_bytes > budget.max_bytes:
        report.breaches.append(
            f"bytes {report.total_bytes} > {budget.max_bytes}"
        )
    if (budget.max_blocking_ms is not None
            and report.blocking_ms > budget.max_blocking_ms):
        report.breaches.append(
            f"blocking_ms {report.blocking_ms:.1f} > {budget.max_blocking_ms}"
        )
    if budget.max_vendors is not None and len(vendors) > budget.max_vendors:
        report.breaches.append(
            f"vendors {len(vendors)} > {budget.max_vendors}"
        )
    return report


def assert_within_budget(report: ThirdPartyReport) -> None:
    if not isinstance(report, ThirdPartyReport):
        raise ThirdPartyBudgetError("assert_within_budget expects ThirdPartyReport")
    if report.passed():
        return
    raise ThirdPartyBudgetError(
        "third-party budget breached — " + "; ".join(report.breaches)
    )
