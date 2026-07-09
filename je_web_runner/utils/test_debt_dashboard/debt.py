"""
盤點 skipped / xfail / TODO 測試項目,附帶 age + owner。
"Just temporarily skipping this until we figure it out" — and then it's
six months later and nobody remembers why. This module scans the test
tree and produces a snapshot of every form of "deferred test work":

* ``@pytest.mark.skip(reason=...)`` and ``@pytest.mark.skipif(...)``
* ``@pytest.mark.xfail(...)``
* ``# TODO`` / ``# FIXME`` comments inside ``def test_*``
* JSON action files with ``"_skip": true`` markers

Each item gets an age (from git blame mtime if available, else file
mtime) and an owner (best-effort from CODEOWNERS).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


from je_web_runner.utils.exception.exceptions import WebRunnerException


class TestDebtDashboardError(WebRunnerException):
    """Raised on bad input paths."""

    __test__ = False  # domain exception, not a pytest test class


class DebtKind(str, Enum):
    SKIP = "skip"
    XFAIL = "xfail"
    TODO = "todo"
    JSON_SKIP = "json_skip"


_SKIP_RE = re.compile(
    r"@pytest\.mark\.skip\s*\(\s*(?:reason\s*=\s*)?[\"']([^\"']*)[\"']",
    re.IGNORECASE,
)
_SKIPIF_RE = re.compile(
    # Greedy `[^)]*` ensures the optional `reason=` group below actually gets a
    # chance to match (with the previous lazy `*?` the engine took 0 chars and
    # skipped reason).
    r"@pytest\.mark\.skipif\s*\([^)]*?reason\s*=\s*[\"']([^\"']*)[\"']",
    re.IGNORECASE,
)
_XFAIL_RE = re.compile(
    r"@pytest\.mark\.xfail\s*\([^)]*?reason\s*=\s*[\"']([^\"']*)[\"']",
    re.IGNORECASE,
)
# NOSONAR python:S5852 — input is one source line at a time (bounded)
_TODO_RE = re.compile(r"#\s*(TODO|FIXME)\b[:\s]*(.*)$", re.IGNORECASE)
_TEST_DEF_RE = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.MULTILINE)


# ---------- data --------------------------------------------------------

@dataclass
class DebtItem:
    """One piece of test debt."""

    kind: DebtKind
    path: str
    line: int
    test_name: str | None
    reason: str
    age_days: float
    owner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "kind": self.kind.value}


@dataclass
class DebtReport:
    """Aggregate across one or many scans."""

    items: list[DebtItem] = field(default_factory=list)

    def by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for item in self.items:
            out[item.kind.value] = out.get(item.kind.value, 0) + 1
        return out

    def by_owner(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for item in self.items:
            key = item.owner or "(unowned)"
            out[key] = out.get(key, 0) + 1
        return out

    def older_than(self, days: float) -> list[DebtItem]:
        return [i for i in self.items if i.age_days >= days]


# ---------- CODEOWNERS lookup ------------------------------------------

@dataclass
class CodeownersIndex:
    """Tiny in-memory CODEOWNERS lookup."""

    rules: list[tuple]  # (glob_pattern, owners_str)

    def owner_for(self, path: str) -> str | None:
        """Last-matching glob wins (Github semantics)."""
        winner: str | None = None
        for pattern, owners in self.rules:
            if _glob_match(pattern, path):
                winner = owners
        return winner


def _glob_match(pattern: str, path: str) -> bool:
    """Very small subset of CODEOWNERS glob — '**' for any-depth match."""
    if pattern == "*":
        return True
    pat = re.escape(pattern).replace(r"\*\*", r".*").replace(r"\*", r"[^/]*")
    if pattern.startswith("/"):
        pat = "^" + pat[1:]
    else:
        pat = "(^|/)" + pat
    pat += "$"
    return re.search(pat, path) is not None


def parse_codeowners(text: str) -> CodeownersIndex:
    """Parse a CODEOWNERS file body into an :class:`CodeownersIndex`."""
    rules: list[tuple] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        owners = " ".join(parts[1:])
        rules.append((pattern, owners))
    return CodeownersIndex(rules=rules)


# ---------- scanners ---------------------------------------------------

def _file_age_days(path: Path, *, now: datetime) -> float:
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return 0.0
    return max(0.0, (now - mtime).total_seconds() / 86400.0)


_DECORATOR_GAP_RE = re.compile(r"\A\s*(?:@[^\n]*\n\s*)*\Z")


def _enclosing_test(text: str, char_offset: int) -> str | None:
    """
    Best-effort: return the test function name associated with ``char_offset``.
    For decorator matches, that's the next ``def test_...`` below (only if
    the gap between offset and the def is whitespace + more decorators).
    Otherwise return the last ``def test_...`` above (TODO-in-body case).
    """
    next_below: str | None = None
    next_below_pos: int = -1
    last_above: str | None = None
    for match in _TEST_DEF_RE.finditer(text):
        if match.start() <= char_offset:
            last_above = match.group(1)
        else:
            next_below = match.group(1)
            next_below_pos = match.start()
            break
    if next_below is not None and next_below_pos > char_offset:
        # Find the line end just after `char_offset` so the gap excludes
        # the decorator line itself.
        gap_start = text.find("\n", char_offset)
        if gap_start == -1:
            gap_start = char_offset
        else:
            gap_start += 1
        gap = text[gap_start:next_below_pos]
        if _DECORATOR_GAP_RE.match(gap):
            return next_below
    return last_above


def scan_python_file(
    path: str | Path,
    *,
    now: datetime | None = None,
    owners: CodeownersIndex | None = None,
) -> list[DebtItem]:
    """Scan a single ``test_*.py`` for skip / xfail / TODO markers."""
    p = Path(path)
    if not p.exists():
        raise TestDebtDashboardError(f"file not found: {p}")
    text = p.read_text(encoding="utf-8", errors="replace")
    moment = now if now is not None else datetime.now(tz=timezone.utc)
    age = _file_age_days(p, now=moment)
    owner = owners.owner_for(str(p)) if owners else None
    items: list[DebtItem] = []
    items.extend(_scan_pattern(p, text, _SKIP_RE, DebtKind.SKIP, age, owner))
    items.extend(_scan_pattern(p, text, _SKIPIF_RE, DebtKind.SKIP, age, owner))
    items.extend(_scan_pattern(p, text, _XFAIL_RE, DebtKind.XFAIL, age, owner))
    items.extend(_scan_todos(p, text, age, owner))
    return items


def _scan_pattern(
    path: Path, text: str, regex: re.Pattern,
    kind: DebtKind, age: float, owner: str | None,
) -> list[DebtItem]:
    out: list[DebtItem] = []
    for match in regex.finditer(text):
        reason = match.group(1) or ""
        line = text.count("\n", 0, match.start()) + 1
        out.append(DebtItem(
            kind=kind, path=str(path), line=line,
            test_name=_enclosing_test(text, match.start()),
            reason=reason.strip(), age_days=age, owner=owner,
        ))
    return out


def _scan_todos(
    path: Path, text: str, age: float, owner: str | None,
) -> list[DebtItem]:
    out: list[DebtItem] = []
    for line_index, raw in enumerate(text.split("\n"), start=1):
        match = _TODO_RE.search(raw)
        if not match:
            continue
        out.append(DebtItem(
            kind=DebtKind.TODO, path=str(path), line=line_index,
            test_name=_enclosing_test(text, sum(
                len(line) + 1 for line in text.split("\n")[:line_index - 1]
            )),
            reason=match.group(2).strip(),
            age_days=age, owner=owner,
        ))
    return out


def scan_action_json(
    path: str | Path,
    *,
    now: datetime | None = None,
    owners: CodeownersIndex | None = None,
) -> list[DebtItem]:
    """Scan a JSON action file for ``"_skip": true`` markers."""
    import json
    p = Path(path)
    if not p.exists():
        raise TestDebtDashboardError(f"file not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    moment = now if now is not None else datetime.now(tz=timezone.utc)
    age = _file_age_days(p, now=moment)
    owner = owners.owner_for(str(p)) if owners else None
    out: list[DebtItem] = []
    for index, action in enumerate(data):
        if isinstance(action, dict) and action.get("_skip"):
            out.append(DebtItem(
                kind=DebtKind.JSON_SKIP, path=str(p), line=index + 1,
                test_name=None,
                reason=str(action.get("_reason") or ""),
                age_days=age, owner=owner,
            ))
    return out


def scan_directory(
    root: str | Path,
    *,
    owners: CodeownersIndex | None = None,
    now: datetime | None = None,
) -> DebtReport:
    """Recursively scan ``root`` for python tests + JSON action files."""
    d = Path(root)
    if not d.is_dir():
        raise TestDebtDashboardError(f"not a directory: {d}")
    report = DebtReport()
    for python_file in sorted(d.rglob("test_*.py")):
        report.items.extend(scan_python_file(python_file, owners=owners, now=now))
    for json_file in sorted(d.rglob("*.json")):
        report.items.extend(scan_action_json(json_file, owners=owners, now=now))
    return report


# ---------- assertions -------------------------------------------------

def assert_under_age_limit(report: DebtReport, *, max_days: float) -> None:
    """Raise if any debt item is older than ``max_days``."""
    if max_days < 0:
        raise TestDebtDashboardError("max_days must be >= 0")
    bad = report.older_than(max_days)
    if bad:
        sample = ", ".join(f"{i.kind.value}@{i.path}:{i.line}" for i in bad[:5])
        more = "" if len(bad) <= 5 else f" (+{len(bad) - 5})"
        raise TestDebtDashboardError(
            f"{len(bad)} debt items older than {max_days} days: {sample}{more}"
        )


def report_markdown(report: DebtReport) -> str:
    """Render a small markdown table for dashboards."""
    if not isinstance(report, DebtReport):
        raise TestDebtDashboardError("expects DebtReport")
    lines = [
        f"### Test debt ({len(report.items)} items)", "",
        "| Kind | Count |", "|------|-------|",
    ]
    for kind, count in sorted(report.by_kind().items()):
        lines.append(f"| {kind} | {count} |")
    return "\n".join(lines) + "\n"
