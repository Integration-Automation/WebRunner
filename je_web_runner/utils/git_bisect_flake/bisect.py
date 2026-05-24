"""
自動 bisect ledger,找出造成某 test 開始失敗的 regression commit。
Manual ``git bisect`` is great but slow: you check out, run, mark good/
bad, repeat. When the ledger already has per-commit pass/fail rows, the
bisect can be data-driven — pick the boundary commit just before the
first failure, with no checkouts at all.

Two modes:

* **Data-only bisect** (offline) — looks at the ledger; useful when the
  failing test ran on every commit (CI matrix). No git access needed.
* **Re-run bisect** (online) — needs a ``CommitProbe`` callable that can
  check out a commit and re-run the test. Classic git-bisect with the
  ledger guiding initial bounds so fewer probes are needed.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class GitBisectFlakeError(WebRunnerException):
    """Raised on malformed ledger, missing test history, or probe failure."""


# ---------- ledger model -----------------------------------------------

@dataclass(frozen=True)
class LedgerEntry:
    """One pass/fail row from the run ledger."""

    commit: str
    test_id: str
    passed: bool
    time: str = ""

    def __post_init__(self) -> None:
        if not self.commit or not isinstance(self.commit, str):
            raise GitBisectFlakeError("LedgerEntry.commit must be non-empty string")
        if not self.test_id or not isinstance(self.test_id, str):
            raise GitBisectFlakeError("LedgerEntry.test_id must be non-empty string")


def load_ledger(path: Union[str, Path]) -> List[LedgerEntry]:
    """Read the standard ledger JSON. Schema: ``{"runs": [{commit, path/test_id, passed}]}``."""
    p = Path(path)
    if not p.exists():
        raise GitBisectFlakeError(f"ledger not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as error:
        raise GitBisectFlakeError(f"ledger not JSON: {error}") from error
    if not isinstance(data, dict) or "runs" not in data:
        raise GitBisectFlakeError("ledger missing 'runs' key")
    runs = data["runs"]
    if not isinstance(runs, list):
        raise GitBisectFlakeError("ledger 'runs' must be a list")
    entries: List[LedgerEntry] = []
    for raw in runs:
        if not isinstance(raw, dict):
            continue
        test_id = raw.get("test_id") or raw.get("path")
        commit = raw.get("commit")
        if not isinstance(test_id, str) or not isinstance(commit, str):
            continue
        entries.append(LedgerEntry(
            commit=commit,
            test_id=test_id,
            passed=bool(raw.get("passed")),
            time=str(raw.get("time") or ""),
        ))
    return entries


# ---------- data-only bisect -------------------------------------------

@dataclass
class BisectResult:
    """Outcome of either bisect mode."""

    test_id: str
    last_good_commit: Optional[str]
    first_bad_commit: Optional[str]
    probes: int = 0
    method: str = "ledger"  # 'ledger' | 'probe'
    history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def bisect_from_ledger(
    entries: Sequence[LedgerEntry],
    commit_order: Sequence[str],
    test_id: str,
) -> BisectResult:
    """
    Walk ``commit_order`` (oldest → newest) and return the boundary where
    ``test_id`` flips from pass to fail. If the test was already failing at
    the oldest known commit, ``last_good_commit`` is ``None``.
    """
    if not entries:
        raise GitBisectFlakeError("entries must be a non-empty sequence")
    if not commit_order:
        raise GitBisectFlakeError("commit_order must be a non-empty sequence")
    if not test_id:
        raise GitBisectFlakeError("test_id must be a non-empty string")
    by_commit: Dict[str, LedgerEntry] = {}
    for entry in entries:
        if entry.test_id != test_id:
            continue
        by_commit[entry.commit] = entry
    if not by_commit:
        raise GitBisectFlakeError(f"no ledger rows for test_id {test_id!r}")
    last_good: Optional[str] = None
    first_bad: Optional[str] = None
    history: List[Dict[str, Any]] = []
    for commit in commit_order:
        entry = by_commit.get(commit)
        if entry is None:
            continue
        history.append({"commit": commit, "passed": entry.passed})
        if entry.passed:
            last_good = commit
            first_bad = None
        elif last_good is not None:
            first_bad = commit
            break
        elif first_bad is None:
            first_bad = commit  # earliest known failure when no good commit seen
    return BisectResult(
        test_id=test_id,
        last_good_commit=last_good,
        first_bad_commit=first_bad,
        probes=0,
        method="ledger",
        history=history,
    )


# ---------- probe-driven bisect ----------------------------------------

CommitProbe = Callable[[str], bool]
"""Callable: commit-sha → True if the test passes when run at that commit."""


def bisect_with_probe(
    commit_order: Sequence[str],
    test_id: str,
    probe: CommitProbe,
    *,
    known_good: Optional[str] = None,
    known_bad: Optional[str] = None,
) -> BisectResult:
    """
    Classic bisect using ``probe``. ``known_good`` / ``known_bad`` clamp
    the search window (typical use: feed them from a prior ledger bisect
    so we converge faster).
    """
    if len(commit_order) < 2:
        raise GitBisectFlakeError("commit_order needs at least 2 commits")
    if not test_id:
        raise GitBisectFlakeError("test_id must be non-empty")
    indices_by_commit = {c: i for i, c in enumerate(commit_order)}
    low = 0
    high = len(commit_order) - 1
    if known_good is not None:
        if known_good not in indices_by_commit:
            raise GitBisectFlakeError(f"known_good {known_good!r} not in commit_order")
        low = indices_by_commit[known_good]
    if known_bad is not None:
        if known_bad not in indices_by_commit:
            raise GitBisectFlakeError(f"known_bad {known_bad!r} not in commit_order")
        high = indices_by_commit[known_bad]
    if low >= high:
        raise GitBisectFlakeError("known_good must come before known_bad in commit_order")

    probes = 0
    history: List[Dict[str, Any]] = []
    while high - low > 1:
        mid = (low + high) // 2
        commit = commit_order[mid]
        try:
            passed = bool(probe(commit))
        except Exception as error:
            raise GitBisectFlakeError(
                f"probe failed at {commit}: {error!r}"
            ) from error
        probes += 1
        history.append({"commit": commit, "passed": passed})
        web_runner_logger.info(
            f"git_bisect_flake probe {probes}: {commit[:8]} passed={passed}"
        )
        if passed:
            low = mid
        else:
            high = mid
    last_good = commit_order[low]
    first_bad = commit_order[high]
    return BisectResult(
        test_id=test_id,
        last_good_commit=last_good,
        first_bad_commit=first_bad,
        probes=probes,
        method="probe",
        history=history,
    )


# ---------- reporting --------------------------------------------------

def report_markdown(result: BisectResult) -> str:
    """Render the result as a small markdown block for PR comments."""
    if not isinstance(result, BisectResult):
        raise GitBisectFlakeError("report_markdown expects BisectResult")
    lines = [
        f"### git-bisect for `{result.test_id}` ({result.method}, {result.probes} probes)",
        "",
    ]
    if result.first_bad_commit is None:
        lines.append("_Test has not flipped in the observed range._")
    else:
        if result.last_good_commit:
            lines.append(f"- Last good commit: `{result.last_good_commit}`")
        else:
            lines.append("- No good commit observed in window.")
        lines.append(f"- First bad commit: `{result.first_bad_commit}`")
    if result.history:
        lines.append("")
        lines.append("| Commit | Passed |")
        lines.append("|--------|--------|")
        for entry in result.history[:10]:
            mark = "✓" if entry.get("passed") else "✗"
            lines.append(f"| `{str(entry.get('commit'))[:10]}` | {mark} |")
        if len(result.history) > 10:
            lines.append(f"_({len(result.history) - 10} earlier rows hidden)_")
    return "\n".join(lines) + "\n"
