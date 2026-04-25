"""
舊命令名遷移工具：把 ``WR_SaveTestObject`` → ``WR_save_test_object`` 等。
Migration helper that rewrites the eleven legacy aliases (see fix #3-#11)
to their preferred names. Other commands are left untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class MigrationError(WebRunnerException):
    """Raised when a file cannot be read or written."""


_LEGACY_TO_NEW: Dict[str, str] = {
    "WR_get_webdriver_manager": "WR_new_driver",
    "WR_quit": "WR_quit_all",
    "WR_single_quit": "WR_quit_current",
    "WR_explict_wait": "WR_explicit_wait",
    "WR_SaveTestObject": "WR_save_test_object",
    "WR_CleanTestObject": "WR_clear_test_objects",
    "WR_find_element": "WR_find_recorded_element",
    "WR_find_elements": "WR_find_recorded_elements",
    "WR_input_to_element": "WR_element_input",
    "WR_click_element": "WR_element_click",
    "WR_element_check_current_web_element": "WR_element_assert",
}


def _migrate_action_list(action_list: List[Any]) -> Tuple[List[Any], List[Dict[str, Any]]]:
    rewritten: List[Any] = []
    changes: List[Dict[str, Any]] = []
    for index, action in enumerate(action_list):
        if isinstance(action, list) and action and isinstance(action[0], str):
            new_name = _LEGACY_TO_NEW.get(action[0])
            if new_name is not None:
                changes.append({
                    "index": index,
                    "from": action[0],
                    "to": new_name,
                })
                rewritten.append([new_name, *action[1:]])
                continue
        rewritten.append(action)
    return rewritten, changes


def migrate_action(data: Any) -> Tuple[Any, List[Dict[str, Any]]]:
    """
    將 action 結構內所有舊命令名改寫為新名
    Rewrite legacy command names to their preferred aliases. Returns
    ``(new_data, changes)``.
    """
    if isinstance(data, list):
        new_list, changes = _migrate_action_list(data)
        return new_list, changes
    if isinstance(data, dict):
        action_list = data.get("webdriver_wrapper")
        if not isinstance(action_list, list):
            return data, []
        new_list, changes = _migrate_action_list(action_list)
        new_data = dict(data)
        new_data["webdriver_wrapper"] = new_list
        return new_data, changes
    return data, []


def migrate_action_file(path: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    Read ``path``, rewrite legacy names, optionally write back when
    ``dry_run`` is False. Returns ``{path, changes, written}``.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise MigrationError(f"action file not found: {path}")
    web_runner_logger.info(f"migrate_action_file: {path} dry_run={dry_run}")
    try:
        with open(file_path, encoding="utf-8") as action_file:
            data = json.load(action_file)
    except ValueError as error:
        raise MigrationError(f"action file not valid JSON: {path}") from error
    new_data, changes = migrate_action(data)
    written = False
    if changes and not dry_run:
        with open(file_path, "w", encoding="utf-8") as action_file:
            json.dump(new_data, action_file, indent=2, ensure_ascii=False)
        written = True
    return {"path": str(file_path), "changes": changes, "written": written}


def migrate_directory(directory: str, dry_run: bool = True) -> List[Dict[str, Any]]:
    """
    遍歷目錄內所有 ``.json`` 檔做遷移
    Walk a directory, migrate every ``.json`` file, return a list of per-file
    summaries.
    """
    base = Path(directory)
    if not base.is_dir():
        raise MigrationError(f"directory not found: {directory}")
    return [
        migrate_action_file(str(json_path), dry_run=dry_run)
        for json_path in sorted(base.rglob("*.json"))
    ]
