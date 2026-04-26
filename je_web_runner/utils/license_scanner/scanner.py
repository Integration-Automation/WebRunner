"""
JS/CSS bundle 中的授權聲明掃描：抓 SPDX 標籤、AGPL/GPL 字樣等。
License-header scanner. Looks for SPDX identifiers and well-known license
strings in concatenated bundle output, so SBOM tooling and CI gates can
fail PRs that pull in copyleft / unsupported licenses.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class LicenseScannerError(WebRunnerException):
    """Raised when the scanner is asked for invalid input or assertion fails."""


@dataclass
class LicenseFinding:
    license_id: str
    line_number: int
    snippet: str


_SPDX_PATTERN = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.\-+_]+)")

_KEYWORD_LICENSES = {
    "AGPL-3.0": [r"GNU AFFERO GENERAL PUBLIC LICENSE.{0,40}3"],
    "GPL-3.0": [r"GNU GENERAL PUBLIC LICENSE.{0,40}3"],
    "LGPL-3.0": [r"GNU LESSER GENERAL PUBLIC LICENSE.{0,40}3"],
    "MIT": [r"\bMIT License\b", r"Permission is hereby granted, free of charge"],
    "BSD-3-Clause": [r"Redistributions in binary form must reproduce"],
    "Apache-2.0": [r"Apache License,?\s*Version 2\.0"],
    "MPL-2.0": [r"Mozilla Public License,?\s*Version 2\.0"],
    "ISC": [r"\bISC License\b"],
    "Unlicense": [r"This is free and unencumbered software"],
}


def scan_text(text: str) -> List[LicenseFinding]:
    """
    從文字內容找出 SPDX/已知授權字樣
    Find every SPDX identifier and known license phrase in ``text``.
    """
    if not isinstance(text, str):
        raise LicenseScannerError("text must be str")
    findings: List[LicenseFinding] = []
    for index, line in enumerate(text.splitlines(), start=1):
        match = _SPDX_PATTERN.search(line)
        if match:
            findings.append(LicenseFinding(
                license_id=match.group(1),
                line_number=index,
                snippet=line.strip()[:200],
            ))
    for license_id, patterns in _KEYWORD_LICENSES.items():
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                line_number = text.count("\n", 0, match.start()) + 1
                snippet = text[max(0, match.start() - 20):match.end() + 30].replace("\n", " ")
                findings.append(LicenseFinding(
                    license_id=license_id,
                    line_number=line_number,
                    snippet=snippet.strip()[:200],
                ))
    findings.sort(key=lambda f: (f.line_number, f.license_id))
    return findings


def summarise(findings: Iterable[LicenseFinding]) -> Counter:
    return Counter(f.license_id for f in findings)


def assert_allowed_licenses(
    findings: Iterable[LicenseFinding],
    allow: Sequence[str],
    deny: Optional[Sequence[str]] = None,
) -> None:
    """
    斷言所有偵測到的授權都在 ``allow``、且不在 ``deny`` 名單中
    Raise unless every finding is in ``allow`` *and* not in ``deny``.
    """
    allow_set = {a.strip() for a in allow}
    deny_set = {d.strip() for d in (deny or [])}
    bad: List[LicenseFinding] = []
    for finding in findings:
        if finding.license_id in deny_set or finding.license_id not in allow_set:
            bad.append(finding)
    if bad:
        sample = [
            {"license": f.license_id, "line": f.line_number} for f in bad[:5]
        ]
        raise LicenseScannerError(f"{len(bad)} disallowed license finding(s): {sample}")
