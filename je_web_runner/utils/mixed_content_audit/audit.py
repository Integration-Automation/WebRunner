"""
偵測 HTTPS 頁面內載入的 HTTP 資源(瀏覽器靜默 block,平常測不出來)。
Modern browsers block "active" mixed content (script/iframe/xhr) silently
and downgrade-upgrade "passive" content (img/video/audio) — both end up
as broken UX. This module parses HAR / console-error / response-header
sources and flags everything that doesn't match the page's secure
origin.

Classification follows MDN's split:

* **Active** — script, link rel=stylesheet, iframe, fetch/XHR, WebSocket
  → BLOCKED outright
* **Passive** — image, audio, video, font → loaded but flagged
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class MixedContentAuditError(WebRunnerException):
    """Raised on malformed HAR / failed assertion."""


class Severity(str, Enum):
    """Mixed-content severity buckets."""

    ACTIVE = "active"      # blocked / broken
    PASSIVE = "passive"    # works but flagged
    UPGRADE = "upgrade"    # browser upgraded http→https automatically


_ACTIVE_TYPES = {
    "script", "stylesheet", "iframe", "subdocument", "xhr", "fetch",
    "websocket", "manifest", "preflight",
}
_PASSIVE_TYPES = {
    "image", "imageset", "media", "video", "audio", "font", "track",
}

# Sites that auto-redirect http→https; this module still flags them as
# "upgrade" so devs can fix the source link, but they're a softer signal.
_HSTS_AUTO_DOMAINS = {"www.google.com", "www.youtube.com", "fonts.googleapis.com"}


# ---------- findings ----------------------------------------------------

@dataclass
class MixedFinding:
    """One http resource on an https page."""

    url: str
    resource_type: str
    severity: Severity
    source_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "severity": self.severity.value}


# ---------- classification ---------------------------------------------

def _classify(resource_type: str) -> Severity:
    rt = (resource_type or "").lower()
    if rt in _ACTIVE_TYPES:
        return Severity.ACTIVE
    if rt in _PASSIVE_TYPES:
        return Severity.PASSIVE
    return Severity.ACTIVE  # default to strict: unknown = active


def _is_http(url: str) -> bool:
    try:
        return urlparse(url).scheme.lower() == "http"
    except (ValueError, AttributeError):
        return False


def _is_https_origin(url: str) -> bool:
    try:
        return urlparse(url).scheme.lower() == "https"
    except (ValueError, AttributeError):
        return False


def _hostname(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except (ValueError, AttributeError):
        return ""


# ---------- scanners ---------------------------------------------------

def scan_har(
    har: Union[str, Dict[str, Any]],
    *,
    page_url: Optional[str] = None,
) -> List[MixedFinding]:
    """
    Parse a HAR object/string, returning one finding per http request on
    an https page. When ``page_url`` is None, we assume the first entry's
    page URL is the document.
    """
    har_obj = _coerce_har(har)
    entries = ((har_obj.get("log") or {}).get("entries")) or []
    if not isinstance(entries, list):
        raise MixedContentAuditError("har log.entries must be a list")

    document_url = page_url or _first_page_url(har_obj) or ""
    if document_url and not _is_https_origin(document_url):
        return []  # no risk if the page itself is http

    findings: List[MixedFinding] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        request_url = ((entry.get("request") or {}).get("url")) or ""
        if not _is_http(request_url):
            continue
        resource_type = str(
            entry.get("_resourceType")
            or entry.get("resourceType")
            or ""
        )
        severity = _classify(resource_type)
        hostname = _hostname(request_url)
        if hostname in _HSTS_AUTO_DOMAINS:
            severity = Severity.UPGRADE
        findings.append(MixedFinding(
            url=request_url,
            resource_type=resource_type or "unknown",
            severity=severity,
            source_url=document_url,
        ))
    return findings


def _coerce_har(har: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(har, str):
        try:
            parsed = json.loads(har)
        except ValueError as error:
            raise MixedContentAuditError(f"har not JSON: {error}") from error
        if not isinstance(parsed, dict):
            raise MixedContentAuditError("har JSON must be an object")
        return parsed
    if isinstance(har, dict):
        return har
    raise MixedContentAuditError(
        f"scan_har expects str/dict, got {type(har).__name__}"
    )


def _first_page_url(har: Dict[str, Any]) -> Optional[str]:
    pages = ((har.get("log") or {}).get("pages")) or []
    if isinstance(pages, list) and pages:
        first = pages[0]
        if isinstance(first, dict):
            url = first.get("title") or first.get("id")
            if isinstance(url, str) and url.startswith("http"):
                return url
    return None


_MIXED_CONTENT_CONSOLE_RE = re.compile(r"mixed content", re.IGNORECASE)
_ACTIVE_HINT_RE = re.compile(
    r"\b(active|blocked|insecure script|insecure stylesheet|insecure xhr|insecure fetch|insecure iframe)\b",
    re.IGNORECASE,
)


def scan_console_errors(
    messages: Iterable[str],
    *,
    page_url: str = "",
) -> List[MixedFinding]:
    """Heuristic scan over console errors for ``Mixed Content:`` lines."""
    out: List[MixedFinding] = []
    for line in messages:
        if not isinstance(line, str):
            continue
        if not _MIXED_CONTENT_CONSOLE_RE.search(line):
            continue
        http_urls = [u.rstrip(".,;)\"'") for u in re.findall(r"https?://\S+", line)
                     if _is_http(u.rstrip(".,;)\"'"))]
        if not http_urls:
            continue
        url = http_urls[0]
        severity = (
            Severity.ACTIVE if _ACTIVE_HINT_RE.search(line) else Severity.PASSIVE
        )
        out.append(MixedFinding(
            url=url or "(unknown)",
            resource_type="console",
            severity=severity,
            source_url=page_url,
        ))
    return out


# ---------- assertions -------------------------------------------------

def assert_no_active(findings: Sequence[MixedFinding]) -> None:
    """Raise if any active-mixed-content finding is present."""
    actives = [f for f in findings if f.severity == Severity.ACTIVE]
    if actives:
        sample = ", ".join(f.url for f in actives[:3])
        more = "" if len(actives) <= 3 else f" (+{len(actives) - 3} more)"
        raise MixedContentAuditError(f"active mixed content: {sample}{more}")


def assert_clean(findings: Sequence[MixedFinding]) -> None:
    """Raise if any finding is present (strictest)."""
    if findings:
        sample = ", ".join(f"{f.severity.value}:{f.url}" for f in findings[:3])
        more = "" if len(findings) <= 3 else f" (+{len(findings) - 3} more)"
        raise MixedContentAuditError(f"mixed content detected: {sample}{more}")


def summary(findings: Sequence[MixedFinding]) -> Dict[str, int]:
    """Return ``{severity: count}`` summary."""
    out: Dict[str, int] = {}
    for f in findings:
        out[f.severity.value] = out.get(f.severity.value, 0) + 1
    return out
