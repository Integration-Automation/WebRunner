"""
Test-blame ownership lookup.

Given a test name and the project's ``CODEOWNERS`` (GitHub style) plus
``git blame`` history for the test file, decide who to ping when the
test fails. Falls back through:

1. Closest matching CODEOWNERS rule for the test path.
2. Author with the most lines remaining in the test (from blame).
3. Most-recent committer (HEAD).
4. Project-wide default owner (caller-supplied).
"""
from __future__ import annotations

import fnmatch
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class BlameOwnerError(WebRunnerException):
    """Raised on malformed inputs."""


@dataclass
class BlameLine:
    author: str = ""
    commit: str = ""


@dataclass
class CodeownersRule:
    pattern: str
    owners: list[str] = field(default_factory=list)


def parse_codeowners(text: str) -> list[CodeownersRule]:
    if not isinstance(text, str):
        raise BlameOwnerError("CODEOWNERS text must be a string")
    rules: list[CodeownersRule] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern, *owners = parts
        rules.append(CodeownersRule(pattern=pattern,
                                    owners=[o.lstrip("@") for o in owners]))
    return rules


def _glob_match(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        pattern += "**"
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, "**/" + pattern)


def owners_from_codeowners(
    rules: Sequence[CodeownersRule], test_path: str,
) -> list[str]:
    """The *last* matching rule wins, per GitHub semantics."""
    if not isinstance(test_path, str) or not test_path:
        raise BlameOwnerError("test_path must be non-empty")
    selected: CodeownersRule | None = None
    for rule in rules:
        if _glob_match(test_path, rule.pattern):
            selected = rule
    return list(selected.owners) if selected else []


def owners_from_blame(
    blame: Iterable[BlameLine],
) -> list[str]:
    counts = Counter(b.author for b in blame if b.author)
    return [name for name, _ in counts.most_common(3)]


@dataclass
class OwnerVerdict:
    primary: str
    backups: list[str] = field(default_factory=list)
    source: str = ""   # "codeowners" | "blame" | "head" | "default"


def resolve_owner(
    test_path: str,
    *,
    codeowners: Sequence[CodeownersRule] = (),
    blame: Sequence[BlameLine] = (),
    head_author: str = "",
    default: str = "",
) -> OwnerVerdict:
    """Apply the priority chain to produce a single primary owner."""
    co = owners_from_codeowners(codeowners, test_path)
    if co:
        return OwnerVerdict(primary=co[0], backups=co[1:], source="codeowners")
    bl = owners_from_blame(blame)
    if bl:
        return OwnerVerdict(primary=bl[0], backups=bl[1:], source="blame")
    if head_author:
        return OwnerVerdict(primary=head_author, source="head")
    if default:
        return OwnerVerdict(primary=default, source="default")
    raise BlameOwnerError(
        f"no owner found for {test_path!r} — supply a `default`"
    )


def assert_has_owner(verdict: OwnerVerdict) -> None:
    if not verdict.primary:
        raise BlameOwnerError(
            "verdict.primary is empty — every test must have an owner"
        )
