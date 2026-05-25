"""
Resource hints (preload / prefetch / preconnect) actually-used auditor.

Pages routinely accumulate stale ``<link rel="preload">`` tags that point
at assets the page never actually loads — wasting bytes & confusing the
priority queue. This module:

* Parses ``<link rel="preload|prefetch|preconnect">`` declarations.
* Cross-references against a HAR (or fetched-URL list).
* Flags unused hints + missing hints (e.g. an LCP image with no preload).
* Detects ``preload`` without matching ``as=`` (browser will discard).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ResourceHintsAuditError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


class HintKind(str, Enum):
    PRELOAD = "preload"
    PREFETCH = "prefetch"
    PRECONNECT = "preconnect"
    DNS_PREFETCH = "dns-prefetch"
    MODULEPRELOAD = "modulepreload"


@dataclass
class Hint:
    kind: HintKind
    href: str
    as_: str = ""        # only for preload
    crossorigin: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "kind": self.kind.value}


_LINK_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))',
                      re.IGNORECASE)


def _parse_attrs(tag: str) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for match in _ATTR_RE.finditer(tag):
        key = match.group(1).lower()
        attrs[key] = match.group(2) or match.group(3) or match.group(4) or ""
    return attrs


def parse_hints(html: str) -> List[Hint]:
    if not isinstance(html, str):
        raise ResourceHintsAuditError("html must be a string")
    out: List[Hint] = []
    for tag in _LINK_RE.findall(html):
        attrs = _parse_attrs(tag)
        rel = (attrs.get("rel") or "").lower()
        try:
            kind = HintKind(rel)
        except ValueError:
            continue
        out.append(Hint(
            kind=kind,
            href=attrs.get("href", ""),
            as_=attrs.get("as", ""),
            crossorigin="crossorigin" in tag.lower(),
        ))
    return out


def assert_preload_has_as(hints: Iterable[Hint]) -> None:
    bad = [h for h in hints
           if h.kind == HintKind.PRELOAD and not h.as_]
    if bad:
        raise ResourceHintsAuditError(
            f"{len(bad)} preload(s) missing as= attribute → browser will "
            f"discard them: {[b.href for b in bad]}"
        )


def find_unused_hints(
    hints: Sequence[Hint], used_urls: Iterable[str],
) -> List[Hint]:
    used = {u for u in used_urls if isinstance(u, str)}
    return [h for h in hints
            if h.kind in (HintKind.PRELOAD, HintKind.PREFETCH,
                          HintKind.MODULEPRELOAD)
            and h.href
            and h.href not in used
            and not any(u.endswith(h.href) or h.href.endswith(u)
                        for u in used)]


def assert_no_unused_hints(
    hints: Sequence[Hint], used_urls: Iterable[str],
) -> None:
    unused = find_unused_hints(hints, used_urls)
    if unused:
        raise ResourceHintsAuditError(
            f"{len(unused)} unused resource hint(s): "
            f"{[u.href for u in unused]}"
        )


def assert_origin_preconnected(
    hints: Iterable[Hint], *, origin: str,
) -> None:
    if not origin:
        raise ResourceHintsAuditError("origin must be non-empty")
    for h in hints:
        if h.kind == HintKind.PRECONNECT and (h.href == origin
                                              or h.href.rstrip("/") == origin.rstrip("/")):
            return
    raise ResourceHintsAuditError(
        f"no <link rel='preconnect' href='{origin}'> found"
    )
