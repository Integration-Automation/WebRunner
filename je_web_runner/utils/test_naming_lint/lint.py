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
from typing import Iterable

from je_web_runner.utils.exception.exceptions import WebRunnerException


class NamingLintError(WebRunnerException):
    """Raised on assertion failure or malformed input."""


class Convention(str, Enum):
    SHOULD_WHEN = "snake_case_should_when"
    GIVEN_WHEN_THEN = "given_when_then"
    CAMEL_SUBJECT = "camel_subject"


_SEGMENT_RE = re.compile(r"^[a-z0-9](?:[a-z0-9_]*[a-z0-9])?$")


def _matches_should_when(name: str) -> bool:
    if not name.startswith("test_should_"):
        return False
    rest = name[len("test_should_"):]
    if "_when_" not in rest:
        return False
    before, _, after = rest.rpartition("_when_")
    return bool(_SEGMENT_RE.match(before) and _SEGMENT_RE.match(after))


def _matches_given_when_then(name: str) -> bool:
    if not name.startswith("test_given_"):
        return False
    rest = name[len("test_given_"):]
    if "_when_" not in rest or "_then_" not in rest:
        return False
    g_and_w, _, t = rest.rpartition("_then_")
    g, _, w = g_and_w.rpartition("_when_")
    return all(_SEGMENT_RE.match(s) for s in (g, w, t))


_CAMEL_RE = re.compile(r"^test_[a-z][a-z0-9]*[A-Z]\w+$")


def _matches_camel(name: str) -> bool:
    return bool(_CAMEL_RE.match(name))


_MATCHERS = {
    Convention.SHOULD_WHEN: _matches_should_when,
    Convention.GIVEN_WHEN_THEN: _matches_given_when_then,
    Convention.CAMEL_SUBJECT: _matches_camel,
}


@dataclass
class NamingFinding:
    rule: str
    test: str
    message: str


def lint_test_name(
    name: str, *, convention: Convention,
    max_length: int = 100,
) -> list[NamingFinding]:
    if not isinstance(name, str):
        raise NamingLintError("name must be string")
    if not isinstance(convention, Convention):
        raise NamingLintError("convention must be Convention enum")
    if max_length < 10:
        raise NamingLintError("max_length must be >= 10")
    findings: list[NamingFinding] = []
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
    matcher = _MATCHERS[convention]
    if not matcher(name):
        findings.append(NamingFinding(
            rule=f"violates-{convention.value}", test=name,
            message=f"does not match {convention.value} pattern",
        ))
    return findings


def lint_many(
    names: Iterable[str], *, convention: Convention,
    max_length: int = 100,
) -> list[NamingFinding]:
    out: list[NamingFinding] = []
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
