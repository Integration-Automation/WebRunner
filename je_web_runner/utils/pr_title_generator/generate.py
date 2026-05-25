"""
Suggest a Conventional-Commits PR title from a diff or commit history.

Pure-Python heuristic generator (no LLM dependency) that:

* Detects ``feat`` / ``fix`` / ``docs`` / ``test`` / ``refactor`` / ``chore`` /
  ``ci`` / ``build`` / ``perf`` types from file paths and added lines.
* Extracts a likely scope from the top-level changed directory.
* Compresses the most common commit verb into a 1-line summary that fits
  the 72-char Conventional Commits limit.
* Optional LLM hook ([[failure_auto_tag]]-style ``Callable``) for projects
  that want a smarter summary.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PrTitleGeneratorError(WebRunnerException):
    """Raised when inputs are malformed."""


# rough path → type
_PATH_TYPE_RULES = [
    (re.compile(r"(^|/)test(s)?/"), "test"),
    (re.compile(r"(^|/)docs?/"), "docs"),
    (re.compile(r"\.md$"), "docs"),
    (re.compile(r"\.github/workflows/|(^|/)ci/"), "ci"),
    (re.compile(r"(package\.json|pyproject\.toml|requirements.*\.txt|Dockerfile)$"),
     "build"),
]


_VERB_PREFIX = re.compile(
    r"^(add(?:ed|s)?|fix(?:ed|es)?|remove[ds]?|update[ds]?|refactor(?:ed)?|"
    r"bump(?:ed)?|introduce[ds]?|improve[ds]?|drop(?:ped)?|rename(?:d)?|"
    r"clean(?:up|ed)?|implement(?:ed)?)\s+",
    re.IGNORECASE,
)


@dataclass
class DiffStat:
    files: List[str]
    additions: int = 0
    deletions: int = 0


def _classify_type(files: Sequence[str], commits: Sequence[str]) -> str:
    if any(re.search(r"^fix[(:]", c.strip(), re.IGNORECASE) for c in commits):
        return "fix"
    if any("fix" in c.lower()[:40] for c in commits):
        return "fix"
    type_votes: Counter = Counter()
    for path in files:
        for pattern, t in _PATH_TYPE_RULES:
            if pattern.search(path):
                type_votes[t] += 1
                break
    if type_votes:
        return type_votes.most_common(1)[0][0]
    if any("perf" in c.lower() for c in commits):
        return "perf"
    if any("refactor" in c.lower() for c in commits):
        return "refactor"
    return "feat"


def _infer_scope(files: Sequence[str]) -> str:
    tops = Counter()
    for path in files:
        parts = path.replace("\\", "/").split("/")
        # use second segment if path is "src/<scope>/..."
        if len(parts) >= 3 and parts[0] in ("src", "lib", "je_web_runner"):
            tops[parts[1]] += 1
        elif parts:
            tops[parts[0]] += 1
    if not tops:
        return ""
    scope = tops.most_common(1)[0][0]
    return scope[:24]


def _summary_from_commits(commits: Sequence[str]) -> str:
    if not commits:
        return "update"
    msg = commits[0].strip().splitlines()[0]
    msg = msg.lstrip("- *#").strip()
    msg = _VERB_PREFIX.sub("", msg)
    return msg or "update"


def suggest_title(
    files: Sequence[str],
    commits: Sequence[str],
    breaking: bool = False,
) -> str:
    """Return ``type(scope): summary``, breaking-change marker if requested."""
    if not isinstance(files, (list, tuple)):
        raise PrTitleGeneratorError("files must be a sequence of strings")
    if not isinstance(commits, (list, tuple)):
        raise PrTitleGeneratorError("commits must be a sequence of strings")
    if not files and not commits:
        raise PrTitleGeneratorError("need at least one file or commit")
    type_ = _classify_type(files, commits)
    scope = _infer_scope(files)
    summary = _summary_from_commits(commits) if commits else f"update {scope or 'project'}"
    summary = summary[:1].lower() + summary[1:] if summary else summary
    head = f"{type_}({scope})" if scope else type_
    if breaking:
        head += "!"
    title = f"{head}: {summary}"
    if len(title) > 72:
        title = title[:71].rstrip() + "…"
    return title


LlmTitler = Callable[[Sequence[str], Sequence[str]], str]


def suggest_title_with_llm(
    files: Sequence[str],
    commits: Sequence[str],
    titler: LlmTitler,
) -> str:
    if not callable(titler):
        raise PrTitleGeneratorError("titler must be callable")
    try:
        title = titler(files, commits)
    except Exception as error:
        raise PrTitleGeneratorError(f"titler failed: {error!r}") from error
    if not isinstance(title, str) or not title.strip():
        raise PrTitleGeneratorError("titler must return a non-empty string")
    return title.strip()[:72]


def assert_conventional(title: str) -> None:
    if not isinstance(title, str):
        raise PrTitleGeneratorError("title must be string")
    pattern = re.compile(
        r"^(feat|fix|docs|test|refactor|chore|ci|build|perf|style|revert)"
        r"(\([\w\-.]+\))?!?: \S.+",
    )
    if not pattern.match(title):
        raise PrTitleGeneratorError(
            f"title is not Conventional Commits compliant: {title!r}"
        )
