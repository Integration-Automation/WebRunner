"""
PR 級 bundle size delta 報告。
Two HAR snapshots (base branch + PR HEAD) → per-asset delta table →
budget-aware Markdown report for PR comments.

Reuses :mod:`bundle_budget` to classify assets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence, Union

from je_web_runner.utils.bundle_budget.budget import (
    Asset, AssetKind, assets_from_har,
)
from je_web_runner.utils.exception.exceptions import WebRunnerException


class BundleDiffPrError(WebRunnerException):
    """Raised on bad HAR input or bad threshold values."""


# ---------- data --------------------------------------------------------

@dataclass
class AssetDelta:
    """One URL's byte-delta between base and head."""

    url: str
    kind: AssetKind
    base_bytes: int
    head_bytes: int

    @property
    def delta(self) -> int:
        return self.head_bytes - self.base_bytes

    @property
    def percent(self) -> float:
        if self.base_bytes == 0:
            return 100.0 if self.head_bytes > 0 else 0.0
        return (self.delta / self.base_bytes) * 100.0


@dataclass
class BundleDiff:
    """Aggregate base→head diff."""

    added: List[AssetDelta] = field(default_factory=list)
    removed: List[AssetDelta] = field(default_factory=list)
    grew: List[AssetDelta] = field(default_factory=list)
    shrunk: List[AssetDelta] = field(default_factory=list)
    unchanged: int = 0
    total_delta_bytes: int = 0

    def regressions(self, *, min_bytes: int = 1024) -> List[AssetDelta]:
        """Added + grew entries with delta >= ``min_bytes``."""
        if min_bytes < 0:
            raise BundleDiffPrError("min_bytes must be >= 0")
        return [
            d for d in (self.added + self.grew)
            if d.delta >= min_bytes
        ]


# ---------- diff --------------------------------------------------------

def _index(assets: Sequence[Asset]) -> Dict[str, Asset]:
    return {a.url: a for a in assets}


def diff_hars(
    base_har: Union[str, Dict[str, Any]],
    head_har: Union[str, Dict[str, Any]],
) -> BundleDiff:
    """Compare two HAR snapshots; classify URLs as added/removed/grew/shrunk."""
    base = _index(assets_from_har(base_har))
    head = _index(assets_from_har(head_har))
    result = BundleDiff()
    for url, asset in head.items():
        if url not in base:
            delta = AssetDelta(
                url=url, kind=asset.kind,
                base_bytes=0,
                head_bytes=max(asset.transfer_bytes, asset.content_bytes),
            )
            result.added.append(delta)
            result.total_delta_bytes += delta.delta
            continue
        base_asset = base[url]
        base_size = max(base_asset.transfer_bytes, base_asset.content_bytes)
        head_size = max(asset.transfer_bytes, asset.content_bytes)
        if head_size == base_size:
            result.unchanged += 1
            continue
        delta = AssetDelta(
            url=url, kind=asset.kind,
            base_bytes=base_size, head_bytes=head_size,
        )
        result.total_delta_bytes += delta.delta
        (result.grew if delta.delta > 0 else result.shrunk).append(delta)
    for url, asset in base.items():
        if url in head:
            continue
        base_size = max(asset.transfer_bytes, asset.content_bytes)
        delta = AssetDelta(
            url=url, kind=asset.kind,
            base_bytes=base_size, head_bytes=0,
        )
        result.removed.append(delta)
        result.total_delta_bytes += delta.delta
    return result


# ---------- assertions --------------------------------------------------

def assert_under_max_growth(
    diff: BundleDiff, *, max_growth_bytes: int,
) -> None:
    if max_growth_bytes < 0:
        raise BundleDiffPrError("max_growth_bytes must be >= 0")
    if diff.total_delta_bytes > max_growth_bytes:
        raise BundleDiffPrError(
            f"bundle grew by {diff.total_delta_bytes:,}B "
            f"(> budget {max_growth_bytes:,}B)"
        )


# ---------- formatting --------------------------------------------------

def report_markdown(
    diff: BundleDiff, *, top_n: int = 10, min_bytes: int = 1024,
) -> str:
    """Render a small markdown table for PR comments."""
    if not isinstance(diff, BundleDiff):
        raise BundleDiffPrError("report_markdown expects BundleDiff")
    if top_n < 0:
        raise BundleDiffPrError("top_n must be >= 0")
    sign = "▲" if diff.total_delta_bytes >= 0 else "▼"
    lines = [
        f"### Bundle delta: {sign} {diff.total_delta_bytes:+,} bytes",
        "",
        f"- added: {len(diff.added)} files",
        f"- removed: {len(diff.removed)} files",
        f"- grew: {len(diff.grew)} files",
        f"- shrunk: {len(diff.shrunk)} files",
        f"- unchanged: {diff.unchanged} files",
    ]
    regressions = diff.regressions(min_bytes=min_bytes)
    if regressions:
        regressions.sort(key=lambda d: -d.delta)
        lines.append("")
        lines.append("**Largest regressions:**")
        lines.append("| URL | Kind | Δ bytes | Δ % |")
        lines.append("|-----|------|---------|-----|")
        for d in regressions[:top_n]:
            lines.append(
                f"| `{d.url}` | {d.kind.value} | {d.delta:+,} | {d.percent:+.1f}% |"
            )
    return "\n".join(lines) + "\n"
