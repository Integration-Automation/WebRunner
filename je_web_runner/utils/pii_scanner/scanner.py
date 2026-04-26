"""
PII / privacy scanner：偵測 email / phone / 信用卡 / SSN / Taiwan ID 等敏感資料。
PII scanner. Augments :mod:`secrets_scanner` with personal-info detection
on plain text (HAR bodies, OCR'd screenshots, log files).

Detected categories:

- ``email`` — RFC-5322-shaped addresses.
- ``phone_e164`` — international ``+CC...`` numbers, 10-15 digits.
- ``credit_card`` — 13-19 digits passing the Luhn checksum.
- ``ssn_us`` — US SSN ``NNN-NN-NNNN``.
- ``taiwan_id`` — 1 letter + 9 digits, with ROC checksum.
- ``ipv4`` — dotted-quad IPv4 addresses.

Each match returns its category, span, and a redacted preview so the
caller can log without leaking the value.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PiiScannerError(WebRunnerException):
    """Raised when scanning input is invalid or assertion fails."""


@dataclass
class PiiFinding:
    category: str
    start: int
    end: int
    redacted: str


_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}\b"
)
_PHONE_E164_RE = re.compile(r"\+\d{8,15}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_SSN_RE = re.compile(r"\b(?!000|666)(?!9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
_TAIWAN_ID_RE = re.compile(r"\b[A-Z][12]\d{8}\b")
_IPV4_RE = re.compile(
    r"\b(?:25[0-5]|2[0-4]\d|[01]?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d?\d)){3}\b"
)


def _luhn_check(digits: str) -> bool:
    digits_only = [int(c) for c in digits if c.isdigit()]
    if len(digits_only) < 13 or len(digits_only) > 19:
        return False
    total = 0
    parity = (len(digits_only) - 2) % 2
    for index, value in enumerate(digits_only):
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


_TAIWAN_LETTER_VALUES = {
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15, "G": 16, "H": 17,
    "I": 34, "J": 18, "K": 19, "L": 20, "M": 21, "N": 22, "O": 35, "P": 23,
    "Q": 24, "R": 25, "S": 26, "T": 27, "U": 28, "V": 29, "W": 32, "X": 30,
    "Y": 31, "Z": 33,
}


def _taiwan_id_check(value: str) -> bool:
    if len(value) != 10 or value[0] not in _TAIWAN_LETTER_VALUES:
        return False
    head = _TAIWAN_LETTER_VALUES[value[0]]
    digits = [head // 10, head % 10] + [int(c) for c in value[1:]]
    weights = [1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1]
    total = sum(d * w for d, w in zip(digits, weights))
    return total % 10 == 0


def _redact(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def scan_text(text: str, categories: Optional[Sequence[str]] = None) -> List[PiiFinding]:
    """
    對 ``text`` 跑全部或指定的 PII 偵測類別
    Run every (or a filtered subset of) PII detector against ``text``.
    """
    if not isinstance(text, str):
        raise PiiScannerError("text must be str")
    allowed = set(categories) if categories else None
    findings: List[PiiFinding] = []
    for category, regex, validator in _DETECTORS:
        if allowed is not None and category not in allowed:
            continue
        for match in regex.finditer(text):
            value = match.group(0)
            if validator is not None and not validator(value):
                continue
            findings.append(PiiFinding(
                category=category,
                start=match.start(),
                end=match.end(),
                redacted=_redact(value),
            ))
    findings.sort(key=lambda f: (f.start, f.category))
    return findings


_DETECTORS = [
    ("email", _EMAIL_RE, None),
    ("phone_e164", _PHONE_E164_RE, None),
    ("credit_card", _CARD_RE, _luhn_check),
    ("ssn_us", _SSN_RE, None),
    ("taiwan_id", _TAIWAN_ID_RE, _taiwan_id_check),
    ("ipv4", _IPV4_RE, None),
]


def summarise(findings: Iterable[PiiFinding]) -> Counter:
    """Count findings by category."""
    return Counter(f.category for f in findings)


def assert_no_pii(text: str, categories: Optional[Sequence[str]] = None,
                  allow_categories: Optional[Sequence[str]] = None) -> None:
    """
    斷言文本中沒有指定類別的 PII；``allow_categories`` 可白名單跳過。
    Raise :class:`PiiScannerError` when any non-allowed category is found.
    """
    allow = set(allow_categories or [])
    findings = [f for f in scan_text(text, categories=categories)
                if f.category not in allow]
    if findings:
        sample = [
            {"category": f.category, "redacted": f.redacted, "at": f.start}
            for f in findings[:5]
        ]
        raise PiiScannerError(f"{len(findings)} PII finding(s): {sample}")


def redact_text(text: str, replacement: str = "[REDACTED]",
                categories: Optional[Sequence[str]] = None) -> str:
    """Return ``text`` with each PII match replaced by ``replacement``."""
    findings = scan_text(text, categories=categories)
    if not findings:
        return text
    pieces: List[str] = []
    cursor = 0
    for finding in findings:
        if finding.start < cursor:
            continue  # skip overlapping matches
        pieces.append(text[cursor:finding.start])
        pieces.append(replacement)
        cursor = finding.end
    pieces.append(text[cursor:])
    return "".join(pieces)
