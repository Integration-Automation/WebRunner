"""
CODEOWNERS-style file → test → team 對映表。
When a failing test pages someone at 3am, the question "who owns this?"
should have a deterministic answer. This module provides:

* :class:`OwnersFile` — parses a CODEOWNERS-format file (Github semantics).
* :class:`OwnersMap` — adds a per-test override layer (a small YAML/JSON
  file your team controls separately).
* Lookup helpers + bulk audit ("which tests have no owner?").
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class TestOwnersMapError(WebRunnerException):
    """Raised on malformed CODEOWNERS / override file / lookup args."""


# ---------- CODEOWNERS parser -----------------------------------------

@dataclass
class CodeownersRule:
    """One CODEOWNERS line."""

    pattern: str
    owners: List[str] = field(default_factory=list)


@dataclass
class OwnersFile:
    """Parsed CODEOWNERS body. Lookups use *last-matching* glob (Github)."""

    rules: List[CodeownersRule] = field(default_factory=list)

    def lookup(self, path: str) -> List[str]:
        if not isinstance(path, str) or not path:
            raise TestOwnersMapError("path must be non-empty string")
        winner: List[str] = []
        for rule in self.rules:
            if _matches(rule.pattern, path):
                winner = list(rule.owners)
        return winner


# NOSONAR python:S5852 — input is one CODEOWNERS line at a time (bounded)
_COMMENT_STRIP_RE = re.compile(r"\s+#.*$")  # noqa: S5852


def parse_codeowners(text: str) -> OwnersFile:
    """Parse a CODEOWNERS-format string."""
    if not isinstance(text, str):
        raise TestOwnersMapError(
            f"parse_codeowners expects str, got {type(text).__name__}"
        )
    rules: List[CodeownersRule] = []
    for raw in text.splitlines():
        # Strip trailing comments (but keep '#' inside owners like @owner#1)
        line = _COMMENT_STRIP_RE.sub("", raw).strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        rules.append(CodeownersRule(pattern=parts[0], owners=parts[1:]))
    return OwnersFile(rules=rules)


def load_codeowners_file(path: Union[str, Path]) -> OwnersFile:
    """Read and parse a CODEOWNERS file from disk."""
    p = Path(path)
    if not p.exists():
        raise TestOwnersMapError(f"file not found: {p}")
    return parse_codeowners(p.read_text(encoding="utf-8"))


def _matches(pattern: str, path: str) -> bool:
    """Limited CODEOWNERS glob: ``*``, ``**``, dir/, /-anchor."""
    if pattern == "*":
        return True
    is_dir_pattern = pattern.endswith("/")
    pat = pattern.rstrip("/")
    regex = re.escape(pat).replace(r"\*\*", r".*").replace(r"\*", r"[^/]*")
    if pat.startswith("/"):
        regex = "^" + regex[1:]
    else:
        regex = "(^|/)" + regex
    if is_dir_pattern:
        regex += "(/|$)"
    else:
        regex += "$"
    return re.search(regex, path) is not None


# ---------- override layer --------------------------------------------

@dataclass
class OwnersMap:
    """Combined CODEOWNERS + per-test override lookup."""

    codeowners: OwnersFile
    overrides: Dict[str, List[str]] = field(default_factory=dict)

    def owners_for(self, test_id: str) -> List[str]:
        if not isinstance(test_id, str) or not test_id:
            raise TestOwnersMapError("test_id must be non-empty string")
        if test_id in self.overrides:
            return list(self.overrides[test_id])
        return self.codeowners.lookup(test_id)


def load_overrides(path: Union[str, Path]) -> Dict[str, List[str]]:
    """
    Load a per-test override JSON file. Schema:
    ``{"<test_id>": ["@owner1", "@owner2"], ...}``.
    """
    p = Path(path)
    if not p.exists():
        raise TestOwnersMapError(f"overrides file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as error:
        raise TestOwnersMapError(f"overrides not JSON: {error}") from error
    if not isinstance(data, dict):
        raise TestOwnersMapError("overrides JSON must be an object")
    out: Dict[str, List[str]] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise TestOwnersMapError(
                f"override for {key!r} must be a list of strings"
            )
        out[key] = list(value)
    return out


# ---------- audit -----------------------------------------------------

@dataclass
class OwnerAudit:
    """Outcome of :func:`audit_unowned`."""

    total_tests: int
    unowned: List[str] = field(default_factory=list)
    by_owner: Dict[str, int] = field(default_factory=dict)

    def passed(self) -> bool:
        return not self.unowned


def audit_unowned(
    test_ids: Iterable[str],
    owners_map: OwnersMap,
) -> OwnerAudit:
    """Walk ``test_ids``, list any without an owner, count by owner."""
    if not isinstance(owners_map, OwnersMap):
        raise TestOwnersMapError("owners_map must be an OwnersMap")
    audit = OwnerAudit(total_tests=0)
    for test_id in test_ids:
        if not isinstance(test_id, str) or not test_id:
            continue
        audit.total_tests += 1
        owners = owners_map.owners_for(test_id)
        if not owners:
            audit.unowned.append(test_id)
            continue
        for owner in owners:
            audit.by_owner[owner] = audit.by_owner.get(owner, 0) + 1
    return audit


# ---------- assertions / formatting -----------------------------------

def assert_no_unowned(audit: OwnerAudit) -> None:
    """Raise if any test in the audit has no owner."""
    if not isinstance(audit, OwnerAudit):
        raise TestOwnersMapError("expects OwnerAudit")
    if audit.passed():
        return
    sample = ", ".join(audit.unowned[:5])
    more = "" if len(audit.unowned) <= 5 else f" (+{len(audit.unowned) - 5})"
    raise TestOwnersMapError(
        f"{len(audit.unowned)} unowned tests: {sample}{more}"
    )


def audit_markdown(audit: OwnerAudit, *, top_owners: int = 10) -> str:
    """Render a small markdown table for dashboards."""
    if not isinstance(audit, OwnerAudit):
        raise TestOwnersMapError("expects OwnerAudit")
    if top_owners < 0:
        raise TestOwnersMapError("top_owners must be >= 0")
    lines = [
        f"### Test ownership audit ({audit.total_tests} tests)",
        "",
        f"- unowned: **{len(audit.unowned)}**",
        "",
    ]
    if audit.by_owner:
        lines.append("| Owner | Tests |")
        lines.append("|-------|-------|")
        ranked = sorted(audit.by_owner.items(), key=lambda kv: -kv[1])[:top_owners]
        for owner, count in ranked:
            lines.append(f"| {owner} | {count} |")
    return "\n".join(lines) + "\n"
