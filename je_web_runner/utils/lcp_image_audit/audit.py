"""
LCP image preload audit.

If the Largest Contentful Paint element is an image, modern Core Web
Vitals best-practice is to preload it AND mark it ``fetchpriority="high"``.
This module:

* Parses an ``LCP`` candidate description (from
  ``PerformanceObserver('largest-contentful-paint')``).
* Cross-references the HTML/HAR to confirm the image URL appears in
  a ``<link rel="preload" as="image">`` tag or a ``Link:`` header.
* Checks ``loading="lazy"`` is NOT set on the LCP image (a very common
  bug after copy-paste from below-the-fold).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class LcpImageAuditError(WebRunnerException):
    """Raised when an LCP image best-practice fails."""


@dataclass
class LcpCandidate:
    url: str
    element_tag: str = ""
    render_time_ms: float = 0
    size_px: int = 0     # rendered area in CSS px²


def parse_candidate(payload: Any) -> LcpCandidate:
    if not isinstance(payload, dict):
        raise LcpImageAuditError("payload must be a dict")
    url = payload.get("url") or payload.get("src") or ""
    if not isinstance(url, str) or not url:
        raise LcpImageAuditError("payload missing 'url' (or 'src')")
    return LcpCandidate(
        url=url,
        element_tag=str(payload.get("element_tag") or ""),
        render_time_ms=float(payload.get("render_time_ms") or 0),
        size_px=int(payload.get("size_px") or 0),
    )


_PRELOAD_RE = re.compile(
    r'<link\s+[^>]*rel=[\'"]?preload[\'"]?[^>]*'
    r'href=[\'"]([^\'"]+)[\'"][^>]*as=[\'"]?image[\'"]?',
    re.IGNORECASE | re.DOTALL,
)
_PRELOAD_RE_REVERSE = re.compile(
    r'<link\s+[^>]*as=[\'"]?image[\'"]?[^>]*'
    r'href=[\'"]([^\'"]+)[\'"][^>]*rel=[\'"]?preload[\'"]?',
    re.IGNORECASE | re.DOTALL,
)


_HTML_TYPE_ERROR = "html must be a string"


def _extract_preloaded_image_urls(html: str) -> List[str]:
    if not isinstance(html, str):
        raise LcpImageAuditError(_HTML_TYPE_ERROR)
    matches = _PRELOAD_RE.findall(html) + _PRELOAD_RE_REVERSE.findall(html)
    return list(matches)


def assert_lcp_preloaded(
    candidate: LcpCandidate, html: str,
    *, link_header_urls: Sequence[str] = (),
) -> None:
    preloaded = set(_extract_preloaded_image_urls(html)) | set(link_header_urls)
    if candidate.url not in preloaded and not any(
        candidate.url.endswith("/" + u) or u.endswith(candidate.url)
        for u in preloaded
    ):
        raise LcpImageAuditError(
            f"LCP image {candidate.url!r} not in preload set "
            f"({len(preloaded)} preloaded image(s) declared)"
        )


def assert_lcp_not_lazy_loaded(
    candidate: LcpCandidate, html: str,
) -> None:
    if not isinstance(html, str):
        raise LcpImageAuditError(_HTML_TYPE_ERROR)
    pattern = re.compile(
        rf'<img[^>]*src=[\'"]{re.escape(candidate.url)}[\'"][^>]*'
        rf'loading=[\'"]lazy[\'"]',
        re.IGNORECASE,
    )
    if pattern.search(html):
        raise LcpImageAuditError(
            f"LCP image {candidate.url!r} has loading=\"lazy\" — "
            "fetch will be deferred and LCP will be much later"
        )


def assert_fetchpriority_high(
    candidate: LcpCandidate, html: str,
) -> None:
    if not isinstance(html, str):
        raise LcpImageAuditError(_HTML_TYPE_ERROR)
    pattern = re.compile(
        rf'<img[^>]*src=[\'"]{re.escape(candidate.url)}[\'"][^>]*'
        rf'fetchpriority=[\'"]high[\'"]',
        re.IGNORECASE,
    )
    reverse = re.compile(
        rf'<img[^>]*fetchpriority=[\'"]high[\'"][^>]*'
        rf'src=[\'"]{re.escape(candidate.url)}[\'"]',
        re.IGNORECASE,
    )
    if not (pattern.search(html) or reverse.search(html)):
        raise LcpImageAuditError(
            f"LCP image {candidate.url!r} has no fetchpriority=\"high\" — "
            "browser may downgrade its priority"
        )
