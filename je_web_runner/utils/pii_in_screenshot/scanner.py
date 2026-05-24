"""
Screenshot 內個資掃描:OCR → regex,抓出截圖意外洩漏的 email / 信用卡 / 身分證等。
Many staging environments anonymise the DOM but forget images / charts /
PDF previews / 3rd-party iframes. When ``visual_regression`` snapshots
are uploaded to a shared dashboard or attached to a public bundle, those
unredacted PII pieces leak.

This module reuses :mod:`ocr_assert` for text extraction and runs a
focused PII regex set against the output. The PII rules are deliberately
narrower than ``pii_scanner`` (which scans repos / structured payloads)
to keep false positives low on free-form OCR.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Pattern, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.ocr_assert.ocr import OcrBackend, extract_text, normalise_text


class PiiInScreenshotError(WebRunnerException):
    """Raised on bad inputs or OCR failure during scan."""


# ---------- PII rule catalogue ------------------------------------------

@dataclass(frozen=True)
class PiiRule:
    """One PII pattern + label."""

    name: str
    pattern: Pattern[str]
    severity: str = "high"
    # If validator returns False, the match is discarded (e.g. Luhn check).
    validator: Optional[Callable[[str], bool]] = None


def _luhn(card: str) -> bool:
    digits = [int(d) for d in card if d.isdigit()]
    if len(digits) < 12 or len(digits) > 19:
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


_EMAIL = PiiRule(
    name="email",
    pattern=re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    severity="medium",
)
_PHONE_E164 = PiiRule(
    name="phone_e164",
    pattern=re.compile(r"\+\d{1,3}[\s\-.]?\(?\d{1,4}\)?[\s\-.]?\d{2,4}[\s\-.]?\d{2,4}"),
    severity="medium",
)
_CREDIT_CARD = PiiRule(
    name="credit_card",
    # Greedy `[ -]*` consumes any separators eagerly; the outer {13,19} still
    # forces 13-19 digit groups overall (Luhn validator does the real check).
    pattern=re.compile(r"\b(?:\d[ -]*){13,19}\b"),
    severity="critical",
    validator=_luhn,
)
_SSN_US = PiiRule(
    name="ssn_us",
    pattern=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    severity="critical",
)
_TWID = PiiRule(  # Taiwan ID
    name="tw_national_id",
    pattern=re.compile(r"\b[A-Z][12]\d{8}\b"),
    severity="critical",
)
_IBAN = PiiRule(
    name="iban",
    pattern=re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    severity="high",
)
_IPV4 = PiiRule(
    name="ipv4",
    pattern=re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b"
    ),
    severity="low",
)


DEFAULT_RULES: Sequence[PiiRule] = (
    _EMAIL, _PHONE_E164, _CREDIT_CARD, _SSN_US, _TWID, _IBAN, _IPV4,
)


# ---------- findings ----------------------------------------------------

@dataclass
class PiiFinding:
    """One PII occurrence in a screenshot."""

    rule: str
    severity: str
    redacted_match: str
    image: str = ""
    raw_excerpt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _redact_match(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) <= 4:
        return "***"
    return f"{cleaned[:2]}…{cleaned[-2:]}"


# ---------- scan --------------------------------------------------------

def scan_image(
    source: Union[bytes, str, Path, Any],
    *,
    backend: Optional[OcrBackend] = None,
    rules: Sequence[PiiRule] = DEFAULT_RULES,
    image_label: str = "",
) -> List[PiiFinding]:
    """OCR the image and return one :class:`PiiFinding` per (rule, match)."""
    try:
        raw_text = extract_text(source, backend=backend)
    except Exception as error:
        raise PiiInScreenshotError(f"OCR failed: {error!r}") from error
    return _scan_text(raw_text, rules=rules, image_label=image_label)


def scan_text_only(
    text: str,
    *,
    rules: Sequence[PiiRule] = DEFAULT_RULES,
    image_label: str = "",
) -> List[PiiFinding]:
    """Variant for callers that already have OCR'd text in hand."""
    if not isinstance(text, str):
        raise PiiInScreenshotError(
            f"scan_text_only expects str, got {type(text).__name__}"
        )
    return _scan_text(text, rules=rules, image_label=image_label)


def _scan_text(
    text: str,
    *,
    rules: Sequence[PiiRule],
    image_label: str,
) -> List[PiiFinding]:
    findings: List[PiiFinding] = []
    seen: set = set()
    normalised = normalise_text(text, lowercase=False, strip_accents=False)
    for rule in rules:
        for match in rule.pattern.finditer(text):
            value = match.group(0)
            if rule.validator is not None and not rule.validator(value):
                continue
            redacted = _redact_match(value)
            dedup_key = (rule.name, redacted)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            findings.append(PiiFinding(
                rule=rule.name,
                severity=rule.severity,
                redacted_match=redacted,
                image=image_label,
                raw_excerpt=_excerpt_around(normalised, value),
            ))
    return findings


def _excerpt_around(text: str, value: str) -> str:
    idx = text.find(value)
    if idx == -1:
        return ""
    start = max(0, idx - 24)
    end = min(len(text), idx + len(value) + 24)
    excerpt = text[start:end]
    return excerpt.replace(value, "<<PII>>")


# ---------- bulk + assertions -------------------------------------------

@dataclass
class ScanReport:
    """Aggregate over many screenshots."""

    scanned: int = 0
    findings: List[PiiFinding] = field(default_factory=list)
    by_severity: Dict[str, int] = field(default_factory=dict)

    def passed(self) -> bool:
        return not self.findings


def scan_screenshots(
    sources: Sequence[Union[bytes, str, Path, Any]],
    *,
    backend: Optional[OcrBackend] = None,
    rules: Sequence[PiiRule] = DEFAULT_RULES,
) -> ScanReport:
    """Scan a batch of screenshots and return a :class:`ScanReport`."""
    if not sources:
        raise PiiInScreenshotError("sources must be non-empty")
    report = ScanReport()
    for index, source in enumerate(sources):
        label = source if isinstance(source, (str, Path)) else f"image_{index}"
        report.scanned += 1
        for finding in scan_image(
            source, backend=backend, rules=rules, image_label=str(label),
        ):
            report.findings.append(finding)
            report.by_severity[finding.severity] = (
                report.by_severity.get(finding.severity, 0) + 1
            )
    return report


def assert_clean(report: ScanReport) -> None:
    """Raise unless ``report.passed()``."""
    if not isinstance(report, ScanReport):
        raise PiiInScreenshotError("assert_clean expects ScanReport")
    if report.passed():
        return
    sample = ", ".join(
        f"{f.rule}({f.severity})@{f.image}" for f in report.findings[:5]
    )
    more = "" if len(report.findings) <= 5 else f" (+{len(report.findings) - 5})"
    raise PiiInScreenshotError(f"PII detected in screenshots: {sample}{more}")
