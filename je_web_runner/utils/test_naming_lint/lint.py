"""
Test-naming convention linter.

Enforces one of three conventions per file:

* ``snake_case_should_when`` — ``test_should_<verb>_when_<condition>``.
* ``given_when_then`` — ``test_given_<x>_when_<y>_then_<z>``.
* ``camel_subject`` — ``test_<subject><Action>`` (camel after underscore).

Also catches the common smells:

* Test prefix missing (``def login_works`` → invisible to pytest).
* Two leading underscores (``test__weird``) — usually a typo.
* Very long names (> 100 chars) — usually a sign the test does too much.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List

from je_web_runner.utils.exception.exceptions import WebRunnerException


class NamingLintError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


class Convention(str, Enum):
    SHOULD_WHEN = "snake_case_should_when"
    GIVEN_WHEN_THEN = "given_when_then"
    CAMEL_SUBJECT = "camel_subject"


# Patterns avoid nested quantifiers — alternation over a fixed segment set
# keeps the matcher linear regardless of input length.
_PATTERNS = {
    Convention.SHOULD_WHEN: re.compile(
        r"^test_should_[a-z0-9][a-z0-9_]*_when_[a-z0-9][a-z0-9_]*$",
    ),
    Convention.GIVEN_WHEN_THEN: re.compile(
        r"^test_given_[a-z0-9][a-z0-9_]*_when_[a-z0-9][a-z0-9_]*"
        r"_then_[a-z0-9][a-z0-9_]*$",
    ),
    Convention.CAMEL_SUBJECT: re.compile(r"^test_[a-z][a-z0-9]*[A-Z]\w+$"),
}


@dataclass
class NamingFinding:
    rule: str
    test: str
    message: str


def lint_test_name(
    name: str, *, convention: Convention,
    max_length: int = 100,
) -> List[NamingFinding]:
    if not isinstance(name, str):
        raise NamingLintError("name must be string")
    if not isinstance(convention, Convention):
        raise NamingLintError("convention must be Convention enum")
    if max_length < 10:
        raise NamingLintError("max_length must be >= 10")
    findings: List[NamingFinding] = []
    if not name.startswith("test_"):
        findings.append(NamingFinding(
            rule="missing-prefix", test=name,
            message="test function name must start with 'test_'",
        ))
        return findings
    if name.startswith("test__"):
        findings.append(NamingFinding(
            rule="double-underscore", test=name,
            message="leading double underscore is usually a typo",
        ))
    if len(name) > max_length:
        findings.append(NamingFinding(
            rule="too-long", test=name,
            message=f"name length {len(name)} > {max_length}",
        ))
    pattern = _PATTERNS[convention]
    if not pattern.match(name):
        findings.append(NamingFinding(
            rule=f"violates-{convention.value}", test=name,
            message=f"does not match {convention.value} pattern",
        ))
    return findings


def lint_many(
    names: Iterable[str], *, convention: Convention,
    max_length: int = 100,
) -> List[NamingFinding]:
    out: List[NamingFinding] = []
    for n in names:
        out.extend(lint_test_name(n, convention=convention,
                                  max_length=max_length))
    return out


def assert_clean(findings: Iterable[NamingFinding]) -> None:
    items = list(findings)
    if items:
        details = [f"{f.test} ({f.rule})" for f in items[:5]]
        raise NamingLintError(
            f"{len(items)} naming finding(s): {details}"
            + ("…" if len(items) > 5 else "")
        )
