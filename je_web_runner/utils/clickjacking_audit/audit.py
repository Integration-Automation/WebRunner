"""
X-Frame-Options / CSP `frame-ancestors` 驗證 + iframe 嵌入探測。
Two layers of defence against clickjacking:

* **Header policy** — ``X-Frame-Options`` (deprecated but still honored) +
  ``Content-Security-Policy: frame-ancestors`` (modern). At least one
  should be present and restrict third-party framing.
* **Practical probe** — render a tiny test page that loads the target in
  an ``<iframe>``; if the browser actually allows it, the policy is too
  loose regardless of headers.

This module handles the *parsing* and *probe-page generation*; the actual
HTTP fetch / browser load is delegated to caller-supplied callables so
the module stays driver-agnostic.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ClickjackingAuditError(WebRunnerException):
    """Raised on bad header input or failed assertion."""


class Verdict(str, Enum):
    """High-level decision."""

    STRICT = "strict"        # DENY / 'none' — no embedding allowed
    SAMEORIGIN = "sameorigin"  # SAMEORIGIN / 'self' — own origin only
    ALLOWED = "allowed"      # specific origins or all — third party may embed
    MISSING = "missing"      # no policy at all


# ---------- parsing ----------------------------------------------------

_CSP_FRAME_ANCESTORS_RE = re.compile(
    r"(?:^|;\s*)frame-ancestors\s+([^;]+)", re.IGNORECASE,
)


@dataclass
class HeaderPolicy:
    """Parsed clickjacking-related response headers."""

    x_frame_options: Optional[str] = None
    csp_frame_ancestors: Optional[str] = None

    def normalized_xfo(self) -> str:
        return (self.x_frame_options or "").strip().upper()

    def normalized_fa(self) -> str:
        return (self.csp_frame_ancestors or "").strip().lower()


def parse_response_headers(
    headers: Iterable[Tuple[str, str]],
) -> HeaderPolicy:
    """Parse a header iterable (case-insensitive) into a :class:`HeaderPolicy`."""
    xfo: Optional[str] = None
    csp_fa: Optional[str] = None
    for name, value in headers:
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        n = name.strip().lower()
        if n == "x-frame-options":
            xfo = value.strip()
        elif n == "content-security-policy":
            match = _CSP_FRAME_ANCESTORS_RE.search(value)
            if match:
                csp_fa = match.group(1).strip()
    return HeaderPolicy(x_frame_options=xfo, csp_frame_ancestors=csp_fa)


# ---------- verdict ---------------------------------------------------

def classify(policy: HeaderPolicy) -> Verdict:
    """Return the strictest applicable :class:`Verdict`."""
    if not isinstance(policy, HeaderPolicy):
        raise ClickjackingAuditError("classify expects HeaderPolicy")
    fa = policy.normalized_fa()
    if fa:
        tokens = fa.split()
        if "'none'" in tokens or "none" in tokens:
            return Verdict.STRICT
        if any(t in tokens for t in ("*", "http:", "https:")):
            return Verdict.ALLOWED
        if "'self'" in tokens or "self" in tokens:
            return Verdict.SAMEORIGIN
        return Verdict.ALLOWED
    xfo = policy.normalized_xfo()
    if xfo == "DENY":
        return Verdict.STRICT
    if xfo == "SAMEORIGIN":
        return Verdict.SAMEORIGIN
    if xfo.startswith("ALLOW-FROM"):
        return Verdict.ALLOWED  # specific origin permitted
    return Verdict.MISSING


# ---------- probe page generation -------------------------------------

_PROBE_TEMPLATE = """
<!doctype html>
<html><head><title>WR clickjacking probe</title></head>
<body>
<h1 id="status">probing</h1>
<iframe id="probe" src="%(target_url)s" style="width:400px;height:300px"></iframe>
<script>
const probe = document.getElementById('probe');
const status = document.getElementById('status');
probe.addEventListener('load', function() {
  setTimeout(function() {
    try {
      const ok = probe.contentDocument && probe.contentDocument.body !== null;
      status.textContent = ok ? 'EMBEDDED' : 'BLOCKED';
    } catch (e) {
      // Cross-origin block also throws; that still means the frame loaded.
      status.textContent = 'EMBEDDED_OPAQUE';
    }
  }, 250);
});
probe.addEventListener('error', function() {
  status.textContent = 'BLOCKED';
});
setTimeout(function() {
  if (status.textContent === 'probing') status.textContent = 'TIMEOUT';
}, 5000);
</script>
</body></html>
""".strip()


def build_probe_page(target_url: str) -> str:
    """Render an HTML probe page that tries to embed ``target_url``."""
    if not isinstance(target_url, str) or not target_url:
        raise ClickjackingAuditError("target_url must be non-empty string")
    parsed = urlparse(target_url)
    if parsed.scheme not in ("http", "https"):
        raise ClickjackingAuditError(
            f"target_url must be http(s), got {parsed.scheme!r}"
        )
    return _PROBE_TEMPLATE % {"target_url": target_url}


PROBE_STATUS_SCRIPT = "return document.getElementById('status').textContent;"


# ---------- assertions ------------------------------------------------

@dataclass
class AuditReport:
    """Combined header + probe outcome."""

    target_url: str
    verdict: Verdict
    policy: HeaderPolicy
    probe_status: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def passed(self) -> bool:
        if self.verdict in (Verdict.STRICT, Verdict.SAMEORIGIN):
            if self.probe_status is None:
                return True
            return self.probe_status.upper().startswith("BLOCKED")
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_url": self.target_url,
            "verdict": self.verdict.value,
            "policy": asdict(self.policy),
            "probe_status": self.probe_status,
            "notes": list(self.notes),
            "passed": self.passed(),
        }


def audit(
    target_url: str,
    headers: Iterable[Tuple[str, str]],
    *,
    probe_status: Optional[str] = None,
) -> AuditReport:
    """One-shot: parse headers → classify → (optionally) consider probe."""
    policy = parse_response_headers(headers)
    verdict = classify(policy)
    notes: List[str] = []
    if verdict == Verdict.MISSING:
        notes.append("no X-Frame-Options or frame-ancestors set")
    if verdict == Verdict.ALLOWED:
        notes.append("policy permits third-party embedding")
    if probe_status:
        notes.append(f"probe result: {probe_status}")
    return AuditReport(
        target_url=target_url,
        verdict=verdict,
        policy=policy,
        probe_status=probe_status,
        notes=notes,
    )


def assert_protected(report: AuditReport) -> None:
    """Raise unless the report passes (strict / sameorigin and probe blocked)."""
    if not isinstance(report, AuditReport):
        raise ClickjackingAuditError("assert_protected expects AuditReport")
    if report.passed():
        return
    raise ClickjackingAuditError(
        f"clickjacking risk for {report.target_url!r}: "
        f"verdict={report.verdict.value}, probe={report.probe_status!r}"
    )
