"""
每頁 JS / CSS / image / font 載入大小預算 + 違規清單。
The classic "Lighthouse budget" but driven from a HAR file so it works
inside any E2E framework (Selenium / Playwright / WebDriver BiDi).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class BundleBudgetError(WebRunnerException):
    """Raised on bad HAR / budget input or breached budget."""


class AssetKind(str, Enum):
    SCRIPT = "script"
    STYLESHEET = "stylesheet"
    IMAGE = "image"
    FONT = "font"
    MEDIA = "media"
    DOCUMENT = "document"
    XHR = "xhr"
    OTHER = "other"


_MIME_KIND_MAP = {
    "application/javascript": AssetKind.SCRIPT,
    "application/x-javascript": AssetKind.SCRIPT,
    "text/javascript": AssetKind.SCRIPT,
    "module": AssetKind.SCRIPT,
    "text/css": AssetKind.STYLESHEET,
    "font/woff": AssetKind.FONT,
    "font/woff2": AssetKind.FONT,
    "application/font-woff": AssetKind.FONT,
}

_RESOURCE_TYPE_KIND_MAP = {
    "script": AssetKind.SCRIPT,
    "stylesheet": AssetKind.STYLESHEET,
    "image": AssetKind.IMAGE,
    "imageset": AssetKind.IMAGE,
    "font": AssetKind.FONT,
    "media": AssetKind.MEDIA,
    "video": AssetKind.MEDIA,
    "audio": AssetKind.MEDIA,
    "document": AssetKind.DOCUMENT,
    "xhr": AssetKind.XHR,
    "fetch": AssetKind.XHR,
}


# ---------- assets -----------------------------------------------------

@dataclass
class Asset:
    """One downloaded resource."""

    url: str
    kind: AssetKind
    transfer_bytes: int
    content_bytes: int

    @property
    def hostname(self) -> str:
        try:
            return (urlparse(self.url).hostname or "").lower()
        except (ValueError, AttributeError):
            return ""


def _kind_of(entry: Dict[str, Any]) -> AssetKind:
    resource_type = str(
        entry.get("_resourceType") or entry.get("resourceType") or ""
    ).lower()
    if resource_type in _RESOURCE_TYPE_KIND_MAP:
        return _RESOURCE_TYPE_KIND_MAP[resource_type]
    mime = str(
        ((entry.get("response") or {}).get("content") or {}).get("mimeType") or "",
    ).split(";")[0].strip().lower()
    if mime.startswith("image/"):
        return AssetKind.IMAGE
    if mime.startswith("video/") or mime.startswith("audio/"):
        return AssetKind.MEDIA
    return _MIME_KIND_MAP.get(mime, AssetKind.OTHER)


def _sizes(entry: Dict[str, Any]) -> Tuple[int, int]:
    response = entry.get("response") or {}
    content = response.get("content") or {}
    transfer = response.get("_transferSize") or response.get("bodySize")
    body = content.get("size")
    return (
        max(0, int(transfer or 0)),
        max(0, int(body or transfer or 0)),
    )


def assets_from_har(har: Union[str, Dict[str, Any]]) -> List[Asset]:
    """Reduce a HAR object to a flat list of :class:`Asset`."""
    har_obj = _coerce_har(har)
    entries = ((har_obj.get("log") or {}).get("entries")) or []
    if not isinstance(entries, list):
        raise BundleBudgetError("har log.entries must be a list")
    out: List[Asset] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = ((entry.get("request") or {}).get("url")) or ""
        if not url:
            continue
        transfer, body = _sizes(entry)
        out.append(Asset(
            url=url,
            kind=_kind_of(entry),
            transfer_bytes=transfer,
            content_bytes=body,
        ))
    return out


def _coerce_har(har: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(har, str):
        try:
            parsed = json.loads(har)
        except ValueError as error:
            raise BundleBudgetError(f"har not JSON: {error}") from error
        if not isinstance(parsed, dict):
            raise BundleBudgetError("har JSON must be an object")
        return parsed
    if isinstance(har, dict):
        return har
    raise BundleBudgetError(
        f"assets_from_har expects str/dict, got {type(har).__name__}"
    )


# ---------- budget ------------------------------------------------------

@dataclass(frozen=True)
class Budget:
    """Per-kind size budget (transfer-encoded bytes)."""

    kind: AssetKind
    max_bytes: int

    def __post_init__(self) -> None:
        if self.max_bytes <= 0:
            raise BundleBudgetError("max_bytes must be > 0")


DEFAULT_BUDGETS: Sequence[Budget] = (
    Budget(kind=AssetKind.SCRIPT, max_bytes=350 * 1024),
    Budget(kind=AssetKind.STYLESHEET, max_bytes=100 * 1024),
    Budget(kind=AssetKind.IMAGE, max_bytes=800 * 1024),
    Budget(kind=AssetKind.FONT, max_bytes=150 * 1024),
    Budget(kind=AssetKind.MEDIA, max_bytes=2 * 1024 * 1024),
)


@dataclass
class BudgetBreach:
    """One budget violation."""

    kind: AssetKind
    actual_bytes: int
    max_bytes: int
    over_bytes: int


@dataclass
class BudgetReport:
    """Roll-up returned by :func:`evaluate_budget`."""

    totals: Dict[AssetKind, int] = field(default_factory=dict)
    breaches: List[BudgetBreach] = field(default_factory=list)
    biggest_assets: List[Asset] = field(default_factory=list)

    def passed(self) -> bool:
        return not self.breaches


def evaluate_budget(
    assets: Sequence[Asset],
    budgets: Sequence[Budget] = DEFAULT_BUDGETS,
    *,
    biggest_n: int = 10,
) -> BudgetReport:
    """Aggregate per-kind sizes and compare against ``budgets``."""
    if not assets:
        raise BundleBudgetError("assets must be non-empty")
    if biggest_n < 0:
        raise BundleBudgetError("biggest_n must be >= 0")
    totals: Dict[AssetKind, int] = {}
    for asset in assets:
        totals[asset.kind] = totals.get(asset.kind, 0) + max(
            asset.transfer_bytes, asset.content_bytes,
        )
    breaches: List[BudgetBreach] = []
    for budget in budgets:
        if not isinstance(budget, Budget):
            raise BundleBudgetError("budgets entries must be Budget instances")
        actual = totals.get(budget.kind, 0)
        if actual > budget.max_bytes:
            breaches.append(BudgetBreach(
                kind=budget.kind,
                actual_bytes=actual,
                max_bytes=budget.max_bytes,
                over_bytes=actual - budget.max_bytes,
            ))
    biggest = sorted(
        assets, key=lambda a: -max(a.transfer_bytes, a.content_bytes),
    )[:biggest_n]
    return BudgetReport(totals=totals, breaches=breaches, biggest_assets=biggest)


def assert_within_budget(report: BudgetReport) -> None:
    """Raise unless every budget was respected."""
    if not isinstance(report, BudgetReport):
        raise BundleBudgetError("assert_within_budget expects BudgetReport")
    if report.passed():
        return
    parts = [
        f"{b.kind.value}: {b.actual_bytes}>{b.max_bytes} (+{b.over_bytes})"
        for b in report.breaches
    ]
    raise BundleBudgetError("bundle budget breached — " + "; ".join(parts))


def report_markdown(report: BudgetReport) -> str:
    """Render a small markdown table for PR comments."""
    if not isinstance(report, BudgetReport):
        raise BundleBudgetError("report_markdown expects BudgetReport")
    lines = ["### Bundle budget", "", "| Kind | Bytes |", "|------|-------|"]
    for kind, total in sorted(report.totals.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {kind.value} | {total:,} |")
    if report.breaches:
        lines.append("")
        lines.append("**Breaches:**")
        for b in report.breaches:
            lines.append(
                f"- {b.kind.value}: {b.actual_bytes:,}B > {b.max_bytes:,}B "
                f"(over by {b.over_bytes:,}B)"
            )
    if report.biggest_assets:
        lines.append("")
        lines.append("**Biggest assets:**")
        for asset in report.biggest_assets[:5]:
            lines.append(
                f"- `{asset.url}` ({asset.kind.value}) "
                f"{max(asset.transfer_bytes, asset.content_bytes):,}B"
            )
    return "\n".join(lines) + "\n"
