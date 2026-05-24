"""
掃描 response body / HAR / log,抓 JWT、API key、AWS key、session token 等洩漏。
Complements ``pii_scanner`` (which is about user-data) and
``secrets_scanner`` (which scans repo source) — this one runs at *runtime*
against real network traffic / app log output to catch secrets leaking
back to the client.

Findings are deduped by token suffix so a single leaked key showing up in
200 requests becomes one row, not 200.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Pattern, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class TokenLeakError(WebRunnerException):
    """Raised on malformed inputs to the scanner."""


# ---------- detectors ---------------------------------------------------

@dataclass(frozen=True)
class TokenPattern:
    """One regex + label + minimum-length guard."""

    name: str
    pattern: Pattern[str]
    severity: str = "high"  # 'critical' | 'high' | 'medium' | 'low'
    min_length: int = 0


_JWT = TokenPattern(
    name="jwt",
    pattern=re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    severity="critical",
)
_AWS_ACCESS_KEY = TokenPattern(
    name="aws_access_key_id",
    pattern=re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    severity="critical",
)
_AWS_SECRET = TokenPattern(
    name="aws_secret_access_key_assignment",
    pattern=re.compile(
        # (?i) is set, so [A-Z] already covers a-z — duplicate class avoided.
        r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*['\"]([A-Z0-9/+=]{40})['\"]"
    ),
    severity="critical",
)
_GITHUB_TOKEN = TokenPattern(
    name="github_token",
    pattern=re.compile(r"\bghp_[A-Za-z0-9]{36}\b|\bgho_[A-Za-z0-9]{36}\b"),
    severity="critical",
)
_SLACK_TOKEN = TokenPattern(
    name="slack_token",
    pattern=re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    severity="high",
)
_STRIPE_LIVE = TokenPattern(
    name="stripe_live_secret",
    pattern=re.compile(r"\bsk_live_[0-9A-Za-z]{16,}\b"),
    severity="critical",
)
_GOOGLE_API_KEY = TokenPattern(
    name="google_api_key",
    pattern=re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    severity="high",
)
_GENERIC_AUTH_HEADER = TokenPattern(
    name="bearer_assignment",
    # (?i) is set, so [A-Z] already covers a-z.
    pattern=re.compile(r"(?i)bearer\s+([A-Z0-9._\-+/=]{20,})"),
    severity="high",
)
_GENERIC_SESSION = TokenPattern(
    name="session_token_assignment",
    pattern=re.compile(
        # (?i) is set, so [A-Z] already covers a-z.
        r"(?i)(?:session(?:_?id)?|sid|csrf[_-]?token)\s*[:=]\s*['\"]([A-Z0-9._\-+/=]{20,})['\"]"
    ),
    severity="medium",
)


DEFAULT_PATTERNS: Sequence[TokenPattern] = (
    _JWT,
    _AWS_ACCESS_KEY,
    _AWS_SECRET,
    _GITHUB_TOKEN,
    _SLACK_TOKEN,
    _STRIPE_LIVE,
    _GOOGLE_API_KEY,
    _GENERIC_AUTH_HEADER,
    _GENERIC_SESSION,
)


# ---------- findings ----------------------------------------------------

@dataclass
class TokenFinding:
    """One leak match."""

    pattern: str
    severity: str
    token_suffix: str  # last 6 chars of the matched token (so we don't log the whole thing)
    source: str  # 'response_body' | 'har' | 'log' | caller-provided
    location: str = ""  # url / request id / log line offset

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _redact(token: str) -> str:
    if len(token) <= 8:
        return "***"
    return f"…{token[-6:]}"


def _looks_like_jwt(value: str) -> bool:
    try:
        head, _body, _sig = value.split(".")
    except ValueError:
        return False
    try:
        padded = head + "=" * (-len(head) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        header = json.loads(decoded)
    except ValueError:  # JSONDecodeError is a subclass of ValueError
        return False
    return isinstance(header, dict) and "alg" in header

  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
# ---------- core scan ---------------------------------------------------

def scan_text(
    text: str,
    *,
    source: str = "text",
    location: str = "",
    patterns: Sequence[TokenPattern] = DEFAULT_PATTERNS,
) -> List[TokenFinding]:
    """Apply each pattern against ``text`` and return deduped findings."""
    if not isinstance(text, str):
        raise TokenLeakError(f"scan_text expects str, got {type(text).__name__}")
    seen: set = set()
    findings: List[TokenFinding] = []
    for pattern in patterns:
        for match in pattern.pattern.finditer(text):
            token = match.group(1) if match.groups() else match.group(0)
            if len(token) < pattern.min_length:
                continue
            if pattern.name == "jwt" and not _looks_like_jwt(token):
                continue
            suffix = _redact(token)
            dedup_key = (pattern.name, suffix, source, location)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            findings.append(TokenFinding(
                pattern=pattern.name,
                severity=pattern.severity,
                token_suffix=suffix,
                source=source,
                location=location,
            ))
    return findings  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up


def scan_har(
    har: Union[str, Dict[str, Any]],
    *,
    patterns: Sequence[TokenPattern] = DEFAULT_PATTERNS,
) -> List[TokenFinding]:
    """Scan request/response bodies in a HAR object/string."""
    har_obj = _coerce_har(har)
    entries = ((har_obj.get("log") or {}).get("entries")) or []
    out: List[TokenFinding] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        url = ((entry.get("request") or {}).get("url")) or ""
        for direction in ("request", "response"):
            content = ((entry.get(direction) or {}).get("postData")
                       if direction == "request"
                       else (entry.get("response") or {}).get("content")) or {}
            text = content.get("text") if isinstance(content, dict) else None
            if isinstance(text, str) and text:
                out.extend(scan_text(
                    text,
                    source=f"har.{direction}",
                    location=url,
                    patterns=patterns,
                ))
    return out


def _coerce_har(har: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(har, str):
        try:
            parsed = json.loads(har)
        except ValueError as error:
            raise TokenLeakError(f"har is not valid JSON: {error}") from error
        if not isinstance(parsed, dict):
            raise TokenLeakError("har JSON must be an object")
        return parsed
    if isinstance(har, dict):
        return har
    raise TokenLeakError(f"scan_har expects str/dict, got {type(har).__name__}")


def scan_log_lines(
    lines: Iterable[str],
    *,
    patterns: Sequence[TokenPattern] = DEFAULT_PATTERNS,
) -> List[TokenFinding]:
    """Scan an iterable of log lines (file, stream, ledger)."""
    out: List[TokenFinding] = []
    for index, line in enumerate(lines):
        if not isinstance(line, str):
            continue
        out.extend(scan_text(
            line, source="log", location=f"line:{index + 1}", patterns=patterns,
        ))
    return out


# ---------- helpers -----------------------------------------------------

def assert_no_leaks(findings: Sequence[TokenFinding]) -> None:
    """Raise if ``findings`` is non-empty."""
    if findings:
        summary = ", ".join(
            f"{f.pattern}({f.severity})@{f.source}"
            for f in findings[:5]
        )
        more = "" if len(findings) <= 5 else f" (+{len(findings) - 5} more)"
        raise TokenLeakError(f"token leaks detected: {summary}{more}")


def filter_by_severity(
    findings: Sequence[TokenFinding],
    *,
    minimum: str = "high",
) -> List[TokenFinding]:
    """Keep findings at or above ``minimum`` severity."""
    order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    if minimum not in order:
        raise TokenLeakError(f"unknown severity {minimum!r}; pick from {sorted(order)}")
    threshold = order[minimum]
    return [f for f in findings if order.get(f.severity, 0) >= threshold]
