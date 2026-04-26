"""
Diff-aware test selection：只跑被 git diff 影響到的測試。
Pick only the action files / tests touched by the current branch's diff
against a base ref. The selector defers shelling to ``git`` to a callback
so unit tests can mock it; the real CLI integration uses
:func:`subprocess.check_output`.
"""
from __future__ import annotations

import os
import subprocess  # nosec B404 — argv-only invocation, no shell
from typing import Callable, Iterable, List, Optional, Sequence, Set

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class DiffShardError(WebRunnerException):
    """Raised when git is unavailable or returns invalid output."""


GitRunner = Callable[[Sequence[str]], str]


def _default_git_runner(args: Sequence[str]) -> str:
    cmd = ["git", *args]
    try:
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        out = subprocess.check_output(  # nosec B603 — explicit argv list
            cmd,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise DiffShardError(f"git command failed: {error!r}") from error
    return out


def changed_paths(base_ref: str = "main", git_runner: Optional[GitRunner] = None) -> List[str]:
    """
    Return the list of paths changed between ``base_ref`` and ``HEAD``.
    """
    runner = git_runner or _default_git_runner
    raw = runner(["diff", "--name-only", f"{base_ref}...HEAD"])
    return [line.strip() for line in raw.splitlines() if line.strip()]


def select_action_files(
    candidate_paths: Iterable[str],
    changed: Iterable[str],
    additional_keep: Optional[Iterable[str]] = None,
) -> List[str]:
    """
    從 ``candidate_paths`` 中挑出 ``changed`` 中影響到的子集
    Keep only the candidate paths that are also in ``changed``. ``additional_keep``
    forces inclusion regardless of diff (useful for "core" tests that should
    always run).
    """
    changed_set: Set[str] = {_normalise(p) for p in changed}
    keep_set: Set[str] = {_normalise(p) for p in (additional_keep or [])}
    selected: List[str] = []
    for candidate in candidate_paths:
        normalised = _normalise(candidate)
        if normalised in changed_set or normalised in keep_set:
            selected.append(candidate)
    web_runner_logger.info(
        f"diff_shard kept {len(selected)} of "
        f"{sum(1 for _ in candidate_paths)} candidate paths"
    )
    return selected


def select_for_changed(
    candidate_paths: Iterable[str],
    base_ref: str = "main",
    additional_keep: Optional[Iterable[str]] = None,
    git_runner: Optional[GitRunner] = None,
) -> List[str]:
    """High-level shortcut: query git, then filter."""
    changes = changed_paths(base_ref=base_ref, git_runner=git_runner)
    return select_action_files(
        list(candidate_paths), changes, additional_keep=additional_keep,
    )


def _normalise(path: str) -> str:
    if not path:
        return ""
    expanded = os.path.expanduser(path)
    # Treat \ as a separator regardless of host OS — git diff always emits
    # forward slashes, but a candidate list can be authored on Windows.
    return expanded.replace("\\", "/")
