"""
navigator.share assertions.

The Web Share API can't be driven by Selenium (the share sheet is OS
chrome). This module:

* Installs a shim that records every ``navigator.share(...)`` call.
* Lets the test pre-seed whether the share should resolve or reject
  (AbortError when user cancels).
* Provides ``canShare`` capability detection.

Python-side assertions cover: at-least-one-share happened, payload
shape matches expectations (title/text/url/files), fallback UI surfaced
when canShare returned false.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebShareAssertError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


INSTALL_SCRIPT = r"""
(function (settings) {
  if (window.__wr_share__) return;
  const shares = [];
  const fallbackShown = [];
  navigator.share = async function (data) {
    shares.push({
      title: data && data.title,
      text: data && data.text,
      url: data && data.url,
      filesCount: data && data.files ? data.files.length : 0,
    });
    if (settings && settings.reject) {
      const err = new Error('Share canceled');
      err.name = 'AbortError';
      throw err;
    }
  };
  navigator.canShare = function (data) {
    if (settings && settings.canShare === false) return false;
    return !data || !data.files || (settings && settings.canShareFiles !== false);
  };
  window.__wr_share__ = {
    drainShares: function () { return shares.splice(0); },
    markFallback: function (id) { fallbackShown.push({id, ts: Date.now()}); },
    drainFallbacks: function () { return fallbackShown.splice(0); },
  };
})(arguments[0] || {});
"""


@dataclass
class ShareCall:
    title: Optional[str] = None
    text: Optional[str] = None
    url: Optional[str] = None
    files_count: int = 0


@dataclass
class FallbackEvent:
    id: str = ""
    ts_ms: int = 0


@dataclass
class ShareLog:
    shares: List[ShareCall] = field(default_factory=list)
    fallbacks: List[FallbackEvent] = field(default_factory=list)


def parse_log(payload: Any) -> ShareLog:
    if not isinstance(payload, dict):
        raise WebShareAssertError("payload must be a dict")
    shares: List[ShareCall] = []
    for raw in payload.get("shares") or []:
        if not isinstance(raw, dict):
            continue
        shares.append(ShareCall(
            title=raw.get("title"),
            text=raw.get("text"),
            url=raw.get("url"),
            files_count=int(raw.get("filesCount") or 0),
        ))
    fallbacks: List[FallbackEvent] = []
    for raw in payload.get("fallbacks") or []:
        if not isinstance(raw, dict):
            continue
        fallbacks.append(FallbackEvent(
            id=str(raw.get("id") or ""),
            ts_ms=int(raw.get("ts") or 0),
        ))
    return ShareLog(shares=shares, fallbacks=fallbacks)


def assert_shared(log: ShareLog) -> ShareCall:
    if not log.shares:
        raise WebShareAssertError(
            "page never called navigator.share()"
        )
    return log.shares[0]


def assert_url_origin(log: ShareLog, *, expected_origin: str) -> None:
    if not expected_origin:
        raise WebShareAssertError("expected_origin must be non-empty")
    for s in log.shares:
        if not s.url:
            continue
        origin = urlparse(s.url)
        actual = f"{origin.scheme}://{origin.netloc}"
        if actual != expected_origin:
            raise WebShareAssertError(
                f"share url origin {actual!r} != expected {expected_origin!r}"
            )


def assert_has_field(log: ShareLog, *, field: str) -> None:
    """At least one share must have a non-empty value for ``field``."""
    if field not in ("title", "text", "url"):
        raise WebShareAssertError(
            "field must be one of 'title', 'text', 'url'"
        )
    if not any(getattr(s, field) for s in log.shares):
        raise WebShareAssertError(
            f"no share call provided a non-empty {field!r}"
        )


def assert_fallback_shown(log: ShareLog) -> None:
    """If the platform lacks Web Share, the page must surface a fallback UI
    (test driver calls ``__wr_share__.markFallback(id)`` from the click
    handler)."""
    if not log.fallbacks:
        raise WebShareAssertError(
            "no fallback UI marked — page has no graceful degradation"
        )
