"""
Test impact analysis：建立 action JSON 檔對 locator / URL / template 的反查表，
給定變更的元件名／URL，回傳所有受影響的 action JSON 檔。
Walks every action JSON file under a directory, indexes the
``test_object_name``, ``url``, ``template``, and ``WR_*`` command names
each file uses, then answers "which files reference X?" queries so
diff-aware test selection can go beyond filename matching.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ImpactAnalysisError(WebRunnerException):
    """Raised when an action JSON file is malformed."""


@dataclass
class ImpactIndex:
    """Reverse index ``{kind: {token: {file_paths}}}``."""

    by_locator: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    by_url: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    by_template: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    by_command: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def files_for_locator(self, name: str) -> List[str]:
        return sorted(self.by_locator.get(name, set()))

    def files_for_url(self, fragment: str) -> List[str]:
        return sorted({
            file for url, files in self.by_url.items()
            for file in files if fragment in url
        })

    def files_for_template(self, name: str) -> List[str]:
        return sorted(self.by_template.get(name, set()))

    def files_for_command(self, command: str) -> List[str]:
        return sorted(self.by_command.get(command, set()))


_ACTIONS_GLOB = "**/*.json"


def build_index(directory: Union[str, Path], glob: str = _ACTIONS_GLOB) -> ImpactIndex:
    """
    走訪 ``directory`` 下所有 action JSON 檔，建立反查表
    Walk ``directory`` for ``*.json`` files and project each one's locators,
    URLs, templates, and command names into the returned index.
    """
    base = Path(directory)
    if not base.is_dir():
        raise ImpactAnalysisError(f"directory missing: {directory!r}")
    index = ImpactIndex()
    for path in sorted(base.glob(glob)):
        if not path.is_file():
            continue
        try:
            actions = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            web_runner_logger.warning(f"impact_analysis skipping {path}: {error}")
            continue
        if not isinstance(actions, list):
            continue
        _index_actions(index, str(path), actions)
    return index


def _index_actions(index: ImpactIndex, file_path: str, actions: List[Any]) -> None:
    for action in actions:
        if not isinstance(action, list) or not action:
            continue
        command = str(action[0])
        index.by_command[command].add(file_path)
        kwargs = _extract_kwargs(action)
        for key, value in kwargs.items():
            if not isinstance(value, str):
                continue
            if key in {"test_object_name", "element_name"}:
                index.by_locator[value].add(file_path)
            elif key == "url":
                index.by_url[value].add(file_path)
            elif key == "template":
                index.by_template[value].add(file_path)


def _extract_kwargs(action: List[Any]) -> Dict[str, Any]:
    if len(action) >= 3 and isinstance(action[2], dict):
        return action[2]
    if len(action) >= 2 and isinstance(action[1], dict):
        return action[1]
    return {}


def affected_action_files(
    index: ImpactIndex,
    locators: Optional[Iterable[str]] = None,
    urls: Optional[Iterable[str]] = None,
    templates: Optional[Iterable[str]] = None,
    commands: Optional[Iterable[str]] = None,
) -> List[str]:
    """
    Given changed locator/URL/template/command names, return every action
    JSON file that touches at least one of them.
    """
    affected: Set[str] = set()
    for name in locators or []:
        affected.update(index.files_for_locator(name))
    for fragment in urls or []:
        affected.update(index.files_for_url(fragment))
    for template in templates or []:
        affected.update(index.files_for_template(template))
    for command in commands or []:
        affected.update(index.files_for_command(command))
    return sorted(affected)
