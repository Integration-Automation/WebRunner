"""
Heuristic + LLM-assisted failure auto-tagger.

Given a failure bundle (exception text, last action, last console messages,
last network errors), produce a small set of tags (``flaky-locator``,
``network-5xx``, ``js-error``, ``timeout``, ``selector-stale`` …) plus an
optional one-line summary. Tags feed [[flake_detector]],
[[live_dashboard]] aggregation, and PR-triage automations.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FailureAutoTagError(WebRunnerException):
    """Raised when an input bundle is malformed."""


@dataclass
class FailureBundle:
    """Inputs auto-tagger needs (all optional but at least one required)."""

    exception_text: str = ""
    last_action: str = ""
    console_errors: List[str] = field(default_factory=list)
    network_errors: List[Dict[str, Any]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.exception_text or self.last_action
                    or self.console_errors or self.network_errors)


@dataclass
class Tag:
    name: str
    confidence: float = 1.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# pattern -> tag.  Order matters: first hit wins per rule, but every rule
# is evaluated so multiple tags can fire.
_PATTERN_TAGS: List[tuple] = [
    (re.compile(r"NoSuchElement|element not found|locator did not match",
                re.IGNORECASE), "flaky-locator",
     "Selector did not resolve to an element."),
    (re.compile(r"StaleElement|stale element reference", re.IGNORECASE),
     "selector-stale", "DOM moved between locate and act."),
    (re.compile(r"TimeoutException|wait.* timed out|Navigation timeout",
                re.IGNORECASE), "timeout",
     "Wait condition exceeded its budget."),
    (re.compile(r"ElementClickIntercepted|other element would receive the click",
                re.IGNORECASE), "click-intercepted",
     "An overlay covered the target element."),
    (re.compile(r"InvalidSessionId|invalid session id|session deleted",
                re.IGNORECASE), "session-lost",
     "WebDriver session was killed mid-test."),
    (re.compile(r"AssertionError|expected .* got ", re.IGNORECASE),
     "assertion-failed", "An explicit assertion failed."),
]


def _network_tag(bundle: FailureBundle) -> Optional[Tag]:
    server_errors = [e for e in bundle.network_errors
                     if isinstance(e, dict) and 500 <= int(e.get("status", 0)) < 600]
    if server_errors:
        urls = ", ".join(str(e.get("url", "?")) for e in server_errors[:3])
        return Tag(name="network-5xx", confidence=1.0,
                   reason=f"Backend 5xx during run: {urls}")
    failed = [e for e in bundle.network_errors
              if isinstance(e, dict) and int(e.get("status", 0)) >= 400]
    if failed:
        return Tag(name="network-4xx", confidence=0.7,
                   reason="Client-side HTTP error during run.")
    return None


def _console_tag(bundle: FailureBundle) -> Optional[Tag]:
    if any("Uncaught" in c or "TypeError" in c or "ReferenceError" in c
           for c in bundle.console_errors):
        return Tag(name="js-error", confidence=0.9,
                   reason="JS exception logged in console.")
    return None


def heuristic_tags(bundle: FailureBundle) -> List[Tag]:
    """Cheap, deterministic tag pass — no LLM required."""
    if not isinstance(bundle, FailureBundle):
        raise FailureAutoTagError("bundle must be FailureBundle")
    if bundle.is_empty():
        raise FailureAutoTagError("bundle has no signal to tag on")
    tags: List[Tag] = []
    text = bundle.exception_text or ""
    for pattern, name, reason in _PATTERN_TAGS:
        if pattern.search(text):
            tags.append(Tag(name=name, confidence=0.9, reason=reason))
    net = _network_tag(bundle)
    if net:
        tags.append(net)
    js = _console_tag(bundle)
    if js:
        tags.append(js)
    return tags


# ---------------- optional LLM augmentation ----------------

LlmTagger = Callable[[FailureBundle], Sequence[Dict[str, Any]]]
"""Pluggable LLM hook returning ``[{'name', 'confidence', 'reason'}, ...]``."""


def llm_tags(bundle: FailureBundle, tagger: LlmTagger) -> List[Tag]:
    if not callable(tagger):
        raise FailureAutoTagError("tagger must be callable")
    try:
        raw = tagger(bundle)
    except Exception as error:
        raise FailureAutoTagError(f"llm tagger failed: {error!r}") from error
    if not isinstance(raw, (list, tuple)):
        raise FailureAutoTagError("tagger must return a sequence of tag dicts")
    out: List[Tag] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            continue
        out.append(Tag(
            name=name,
            confidence=float(item.get("confidence") or 0.5),
            reason=str(item.get("reason") or ""),
        ))
    return out


def merge_tags(*streams: Sequence[Tag]) -> List[Tag]:
    """De-duplicate by name, keeping the highest-confidence reason."""
    best: Dict[str, Tag] = {}
    for stream in streams:
        for tag in stream:
            existing = best.get(tag.name)
            if existing is None or tag.confidence > existing.confidence:
                best[tag.name] = tag
    return sorted(best.values(), key=lambda t: (-t.confidence, t.name))


def assert_tagged_with(tags: Sequence[Tag], expected: str) -> None:
    if not any(t.name == expected for t in tags):
        raise FailureAutoTagError(
            f"expected tag {expected!r}, got {[t.name for t in tags]}"
        )
