"""
Subresource Integrity (SRI) hash 缺失偵測 + 正確性驗證。
SRI 是防 CDN 被竄改最便宜的招式。但常見三個錯誤:

1. 完全沒設(``integrity`` 屬性缺失)
2. 有設但 hash 過時(資源變了 hash 沒更新 → 載入失敗)
3. 設了弱算法(sha1 / md5 — 規範要求 sha256+)

This module:

* Parses ``<script>`` / ``<link rel=stylesheet>`` tags from HTML for
  ``integrity`` and ``crossorigin`` attributes.
* Recomputes the expected hash from a resource byte payload.
* Returns per-element findings with verdict (OK / MISSING / WEAK_ALG /
  HASH_MISMATCH / NO_CROSSORIGIN).
"""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SriVerifyError(WebRunnerException):
    """Raised on bad input or failed assertion."""


class Verdict(str, Enum):
    OK = "ok"
    MISSING = "missing"
    WEAK_ALG = "weak_alg"
    HASH_MISMATCH = "hash_mismatch"
    NO_CROSSORIGIN = "no_crossorigin"
    UNKNOWN_FORMAT = "unknown_format"


# ---------- parsing ----------------------------------------------------

_SCRIPT_RE = re.compile(r"<script\b([^>]*)>", re.IGNORECASE | re.DOTALL)
_LINK_RE = re.compile(r"<link\b([^>]*)>", re.IGNORECASE | re.DOTALL)
_ATTR_RE = re.compile(
    # re.IGNORECASE is set, so [A-Z] also matches lowercase — no need for [a-zA-Z].
    r"""([A-Z_:][-A-Z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
    re.IGNORECASE,
)


@dataclass
class ResourceTag:
    """One parsed ``<script>`` or ``<link>`` element worth checking."""

    tag: str
    url: str
    integrity: str | None = None
    crossorigin: str | None = None
    rel: str | None = None


def _parse_attrs(blob: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in _ATTR_RE.finditer(blob):
        name = match.group(1).lower()
        value = match.group(2) or match.group(3) or match.group(4) or ""
        out[name] = value
    return out


def parse_html(html: str) -> list[ResourceTag]:
    """Extract every ``<script src>`` / ``<link rel=stylesheet href>`` tag."""
    if not isinstance(html, str):
        raise SriVerifyError(f"html must be str, got {type(html).__name__}")
    tags: list[ResourceTag] = []
    for match in _SCRIPT_RE.finditer(html):
        attrs = _parse_attrs(match.group(1))
        if "src" not in attrs:
            continue
        tags.append(ResourceTag(
            tag="script",
            url=attrs["src"],
            integrity=attrs.get("integrity"),
            crossorigin=attrs.get("crossorigin"),
        ))
    for match in _LINK_RE.finditer(html):
        attrs = _parse_attrs(match.group(1))
        rel = (attrs.get("rel") or "").lower()
        if "stylesheet" not in rel:
            continue
        if "href" not in attrs:
            continue
        tags.append(ResourceTag(
            tag="link",
            url=attrs["href"],
            integrity=attrs.get("integrity"),
            crossorigin=attrs.get("crossorigin"),
            rel=rel,
        ))
    return tags


# ---------- hash helpers -----------------------------------------------

_STRONG_ALGS = {"sha256", "sha384", "sha512"}
_KNOWN_ALGS = _STRONG_ALGS | {"sha1", "md5"}


def compute_integrity(payload: bytes, algorithm: str = "sha384") -> str:
    """Compute the SRI ``alg-base64hash`` string for ``payload``."""
    if not isinstance(payload, (bytes, bytearray)):
        raise SriVerifyError(
            f"payload must be bytes, got {type(payload).__name__}"
        )
    alg = algorithm.lower()
    if alg not in _KNOWN_ALGS:
        raise SriVerifyError(f"unknown algorithm {alg!r}")
    digest = hashlib.new(alg, bytes(payload)).digest()
    return f"{alg}-{base64.b64encode(digest).decode('ascii')}"


def _split_integrity(value: str) -> list[tuple]:
    """Return list of (algorithm, expected_b64) tuples."""
    out: list[tuple] = []
    for token in value.split():
        if "-" not in token:
            continue
        alg, _, b64 = token.partition("-")
        out.append((alg.lower(), b64))
    return out


# ---------- verification -----------------------------------------------

@dataclass
class SriFinding:
    """One per-resource verdict."""

    tag: str
    url: str
    verdict: Verdict
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "verdict": self.verdict.value}


def verify_tag(
    tag: ResourceTag,
    *,
    payload: bytes | None = None,
    require_crossorigin: bool = True,
) -> SriFinding:
    """Verify SRI for one parsed tag, optionally re-checking the hash."""
    if not isinstance(tag, ResourceTag):
        raise SriVerifyError("verify_tag expects ResourceTag")
    if not tag.integrity:
        return SriFinding(
            tag=tag.tag, url=tag.url,
            verdict=Verdict.MISSING,
            detail="no 'integrity' attribute",
        )
    pairs = _split_integrity(tag.integrity)
    if not pairs:
        return SriFinding(
            tag=tag.tag, url=tag.url,
            verdict=Verdict.UNKNOWN_FORMAT,
            detail=f"could not parse integrity {tag.integrity!r}",
        )
    weak_algs = [alg for alg, _ in pairs if alg not in _STRONG_ALGS]
    if all(alg in weak_algs for alg, _ in pairs):
        return SriFinding(
            tag=tag.tag, url=tag.url,
            verdict=Verdict.WEAK_ALG,
            detail=f"weak algs only: {weak_algs}",
        )
    if require_crossorigin and _needs_crossorigin(tag) and not tag.crossorigin:
        return SriFinding(
            tag=tag.tag, url=tag.url,
            verdict=Verdict.NO_CROSSORIGIN,
            detail="cross-origin resource must set crossorigin=anonymous",
        )
    if payload is not None:
        for alg, expected in pairs:
            if alg not in _STRONG_ALGS:
                continue
            actual = compute_integrity(payload, alg)
            actual_b64 = actual.split("-", 1)[1]
            if actual_b64 == expected:
                return SriFinding(tag=tag.tag, url=tag.url, verdict=Verdict.OK)
        return SriFinding(
            tag=tag.tag, url=tag.url,
            verdict=Verdict.HASH_MISMATCH,
            detail=f"no {sorted(_STRONG_ALGS)} hash matched payload",
        )
    return SriFinding(tag=tag.tag, url=tag.url, verdict=Verdict.OK)


def _needs_crossorigin(tag: ResourceTag) -> bool:
    """Cross-origin (URL absolute + scheme present) needs ``crossorigin``."""
    # S5332 ok: we are *detecting* an http:// URL here, not making a request.
    return tag.url.startswith(("http://", "https://", "//"))  # NOSONAR S5332 — intentional plain HTTP (localhost/dev-configured endpoint), not a security-sensitive transport


def verify_html(
    html: str,
    *,
    payload_provider: Any | None = None,
    require_crossorigin: bool = True,
) -> list[SriFinding]:
    """Parse + verify every applicable tag in ``html``."""
    findings: list[SriFinding] = []
    for tag in parse_html(html):
        payload: bytes | None = None
        if payload_provider is not None:
            try:
                payload = payload_provider(tag.url)
            except Exception as error:
                raise SriVerifyError(
                    f"payload_provider failed for {tag.url}: {error!r}"
                ) from error
            if payload is not None and not isinstance(payload, (bytes, bytearray)):
                raise SriVerifyError(
                    f"payload_provider must return bytes, got {type(payload).__name__}"
                )
        findings.append(verify_tag(
            tag, payload=payload, require_crossorigin=require_crossorigin,
        ))
    return findings


# ---------- assertion --------------------------------------------------

def assert_all_ok(findings: Sequence[SriFinding]) -> None:
    """Raise if any finding is not OK."""
    bad = [f for f in findings if f.verdict != Verdict.OK]
    if bad:
        sample = ", ".join(f"{f.verdict.value}:{f.url}" for f in bad[:5])
        more = "" if len(bad) <= 5 else f" (+{len(bad) - 5} more)"
        raise SriVerifyError(f"SRI problems detected: {sample}{more}")
