"""
依影響範圍挑選動作檔 / Pick the action files a change can affect.

Two sources, combined:

* ``--affected-by KIND:VALUE``: a locator, URL fragment, template or command named by
  hand; ``@path`` reads one ``KIND:VALUE`` per line from a file (``#`` comments and
  blank lines skipped), so a CI step can write the list.
* ``--changed-since REF``: the action files ``git diff REF...HEAD`` changed, plus every
  file sharing a locator or template with them. A changed setup file that saves the
  ``login_button`` test object pulls in each test that uses ``login_button``. URLs and
  commands are not followed: almost every file shares them.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

from je_web_runner.utils.impact_analysis.indexer import ImpactAnalysisError, ImpactIndex, build_index
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.sharding import diff_shard

KINDS = ("locator", "url", "template", "command")


def _key(path: str | os.PathLike) -> str:
    return os.path.normcase(os.path.abspath(path))


def parse_affected(specs: Iterable[str]) -> dict[str, list[str]]:
    """
    解析 ``KIND:VALUE`` 與 ``@file``
    ``{"locator": [...], "url": [...], "template": [...], "command": [...]}`` from
    ``KIND:VALUE`` specs and ``@file`` lists of them.
    """
    affected: dict[str, list[str]] = {kind: [] for kind in KINDS}
    for spec in _expanded(specs):
        kind, separator, value = spec.partition(":")
        if not separator or kind.strip() not in KINDS or not value.strip():
            raise ImpactAnalysisError(f"--affected-by takes KIND:VALUE with KIND one of {list(KINDS)}, got {spec!r}")
        affected[kind.strip()].append(value.strip())
    return affected


def _expanded(specs: Iterable[str]) -> list[str]:
    expanded = []
    for spec in specs:
        if not spec.startswith("@"):
            expanded.append(spec)
            continue
        try:
            lines = Path(spec[1:]).read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise ImpactAnalysisError(f"cannot read {spec[1:]!r}: {error}") from error
        expanded.extend(line.strip() for line in lines if line.strip() and not line.strip().startswith("#"))
    return expanded


def changed_action_files(base_ref: str, git_runner: diff_shard.GitRunner | None = None) -> set[str]:
    """The files ``git diff base_ref...HEAD`` names, as normalised absolute paths."""
    runner = git_runner or diff_shard.run_git
    top = runner(["rev-parse", "--show-toplevel"]).strip()
    return {_key(Path(top) / name) for name in diff_shard.changed_paths(base_ref, git_runner=runner)}


def _names_shared_with(index: ImpactIndex, files: set[str]) -> dict[str, list[str]]:
    """The locators and templates any of ``files`` uses."""
    shared: dict[str, list[str]] = {kind: [] for kind in KINDS}
    for kind, table in (("locator", index.by_locator), ("template", index.by_template)):
        shared[kind] = sorted(name for name, users in table.items() if {_key(user) for user in users} & files)
    return shared


def affected_files(index: ImpactIndex, affected: dict[str, list[str]]) -> set[str]:
    """Every indexed file that uses one of the ``affected`` names."""
    lookups = {"locator": index.files_for_locator, "url": index.files_for_url,
               "template": index.files_for_template, "command": index.files_for_command}
    return {_key(path) for kind, values in affected.items() for value in values for path in lookups[kind](value)}


def select_by_impact(files: Sequence[str], directory: str, affected_by: Sequence[str] = (),
                     changed_since: str | None = None, cache_path: str | None = None,
                     git_runner: diff_shard.GitRunner | None = None) -> list[str]:
    """
    只留下受影響的動作檔（保留原順序）
    Keep the ``files`` (in their order) that ``affected_by`` names reach, and with
    ``changed_since`` the changed action files plus those sharing a locator or template
    with them. ``cache_path`` caches the impact index (see ``build_index``).
    """
    index = build_index(directory, cache_path=cache_path)
    wanted = affected_files(index, parse_affected(affected_by))
    if changed_since:
        changed = changed_action_files(changed_since, git_runner) & {_key(path) for path in files}
        wanted |= changed | affected_files(index, _names_shared_with(index, changed))
    selected = [path for path in files if _key(path) in wanted]
    web_runner_logger.info(f"impact selection kept {len(selected)} of {len(files)} action files")
    return selected
