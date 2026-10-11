"""
Test impact analysis：建立 action JSON 檔對 locator / URL / template 的反查表，
給定變更的元件名／URL，回傳所有受影響的 action JSON 檔。
Walks every action JSON file under a directory, indexes the
``test_object_name``, ``url``, ``template``, and ``WR_*`` command names
each file uses, then answers "which files reference X?" queries so
diff-aware test selection can go beyond filename matching.

``build_index(..., cache_path=...)`` keeps each file's names in a JSON cache
and parses only the files that changed: a file whose modification time and
size match is reused as it is, and one whose time changed (a fresh checkout)
is reused when its SHA-256 still matches.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ImpactAnalysisError(WebRunnerException):
    """Raised when an action JSON file is malformed."""


@dataclass
class ImpactIndex:
    """Reverse index ``{kind: {token: {file_paths}}}``."""

    by_locator: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    by_url: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    by_template: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    by_command: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def files_for_locator(self, name: str) -> list[str]:
        return sorted(self.by_locator.get(name, set()))

    def files_for_url(self, fragment: str) -> list[str]:
        return sorted({
            file for url, files in self.by_url.items()
            for file in files if fragment in url
        })

    def files_for_template(self, name: str) -> list[str]:
        return sorted(self.by_template.get(name, set()))

    def files_for_command(self, command: str) -> list[str]:
        return sorted(self.by_command.get(command, set()))


_ACTIONS_GLOB = "**/*.json"
_CACHE_VERSION = 1
_KINDS = ("commands", "locators", "urls", "templates")


def build_index(directory: str | Path, glob: str = _ACTIONS_GLOB, cache_path: str | Path | None = None) -> ImpactIndex:
    """
    走訪 ``directory`` 下所有 action JSON 檔，建立反查表
    Walk ``directory`` for ``*.json`` files and project each one's locators,
    URLs, templates, and command names into the returned index. With
    ``cache_path``, unchanged files are read from that cache instead of parsed,
    and the cache is rewritten with the current files.
    """
    base = Path(directory)
    if not base.is_dir():
        raise ImpactAnalysisError(f"directory missing: {directory!r}")
    cached = _load_cache(cache_path, base, glob) if cache_path else {}
    current: dict[str, dict[str, Any]] = {}
    index = ImpactIndex()
    prefix = len(str(base)) + 1
    for path in sorted(base.glob(glob)):
        file_stat = path.stat()  # one stat per file: on Windows each costs tens of microseconds
        if not stat.S_ISREG(file_stat.st_mode):
            continue
        key = str(path)[prefix:].replace("\\", "/")
        entry = _entry_for(path, file_stat, cached.get(key))
        current[key] = entry
        if entry["names"] is not None:
            _add_names(index, str(path), entry["names"])
    if cache_path and current != cached:
        _save_cache(cache_path, base, glob, current)
    return index


def _entry_for(path: Path, file_stat: os.stat_result, cached: dict[str, Any] | None) -> dict[str, Any]:
    """This file's cache entry: reused when its time and size, or its SHA-256, still match."""
    if cached and cached.get("mtime_ns") == file_stat.st_mtime_ns and cached.get("size") == file_stat.st_size:
        return cached
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if cached and cached.get("sha256") == digest:
        return {**cached, "mtime_ns": file_stat.st_mtime_ns, "size": file_stat.st_size}
    return {"mtime_ns": file_stat.st_mtime_ns, "size": file_stat.st_size, "sha256": digest,
            "names": _names_in(path, data)}


def _names_in(path: Path, data: bytes) -> dict[str, list[str]] | None:
    """The names one action file uses by kind, or None when it is not an action list."""
    try:
        actions = json.loads(data.decode("utf-8"))
    except ValueError as error:  # UnicodeDecodeError is a ValueError too
        web_runner_logger.warning(f"impact_analysis skipping {path}: {error}")
        return None
    if not isinstance(actions, list):
        return None
    names: dict[str, set[str]] = {kind: set() for kind in _KINDS}
    for action in actions:
        if isinstance(action, list) and action:
            _collect(names, action)
    return {kind: sorted(values) for kind, values in names.items()}


_KIND_OF_KEY = {"test_object_name": "locators", "element_name": "locators", "url": "urls", "template": "templates"}


def _collect(names: dict[str, set[str]], action: list[Any]) -> None:
    names["commands"].add(str(action[0]))
    for key, value in _extract_kwargs(action).items():
        kind = _KIND_OF_KEY.get(key)
        if kind is not None and isinstance(value, str):
            names[kind].add(value)


def _add_names(index: ImpactIndex, file_path: str, names: dict[str, list[str]]) -> None:
    targets = {"commands": index.by_command, "locators": index.by_locator,
               "urls": index.by_url, "templates": index.by_template}
    for kind, values in names.items():
        for value in values:
            targets[kind][value].add(file_path)


def _load_cache(cache_path: str | Path, base: Path, glob: str) -> dict[str, dict[str, Any]]:
    """The cached entries, or nothing when the cache is missing, unreadable or for another tree."""
    try:
        cache = json.loads(Path(cache_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        web_runner_logger.warning(f"impact_analysis ignoring cache {cache_path}: {error}")
        return {}
    matches = (isinstance(cache, dict) and cache.get("version") == _CACHE_VERSION
               and cache.get("directory") == str(base.resolve()) and cache.get("glob") == glob)
    files = cache.get("files") if matches else None
    return files if isinstance(files, dict) else {}


def _save_cache(cache_path: str | Path, base: Path, glob: str, entries: dict[str, dict[str, Any]]) -> None:
    payload = {"version": _CACHE_VERSION, "directory": str(base.resolve()), "glob": glob, "files": entries}
    target = Path(cache_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _extract_kwargs(action: list[Any]) -> dict[str, Any]:
    if len(action) >= 3 and isinstance(action[2], dict):
        return action[2]
    if len(action) >= 2 and isinstance(action[1], dict):
        return action[1]
    return {}


def affected_action_files(
    index: ImpactIndex,
    locators: Iterable[str] | None = None,
    urls: Iterable[str] | None = None,
    templates: Iterable[str] | None = None,
    commands: Iterable[str] | None = None,
) -> list[str]:
    """
    Given changed locator/URL/template/command names, return every action
    JSON file that touches at least one of them.
    """
    affected: set[str] = set()
    for name in locators or []:
        affected.update(index.files_for_locator(name))
    for fragment in urls or []:
        affected.update(index.files_for_url(fragment))
    for template in templates or []:
        affected.update(index.files_for_template(template))
    for command in commands or []:
        affected.update(index.files_for_command(command))
    return sorted(affected)
