"""
Action JSON linter：警告反模式（舊命令名、寫死 URL、危險 script 等）。
Action JSON linter that warns about common anti-patterns. Findings are
``{rule, severity, message, location}`` dicts; severity is ``warning`` or
``info``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ActionLinterError(WebRunnerException):
    """Raised when the input cannot be read or parsed."""


# Map legacy → suggested replacement (mirrors the aliases added in fix #3-#11).
_LEGACY_NAMES: Dict[str, str] = {
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
    "WR_element_get_select": (
        "WR_element_select_by_value / WR_element_select_by_index "
        "/ WR_element_select_by_visible_text"
    ),
}

_DANGEROUS_SCRIPT_COMMANDS = frozenset({
    "WR_execute_script",
    "WR_execute_async_script",
    "WR_pw_evaluate",
    "WR_cdp",
    "WR_pw_cdp",
})

_HARDCODED_URL_RE = re.compile(r"https?://[^\s${}]+")


def _walk_args(value: Any, location: str, findings: List[Dict[str, Any]]) -> None:
    """Recursively scan args for hard-coded URLs."""
    if isinstance(value, str):
        if _HARDCODED_URL_RE.search(value) and "${ENV." not in value and "${ROW." not in value:
            findings.append({
                "rule": "hardcoded_url",
                "severity": "warning",
                "message": f"hard-coded URL {value!r}; consider ${{ENV.X}}",
                "location": location,
            })
        return
    if isinstance(value, dict):
        for key, sub in value.items():
            _walk_args(sub, f"{location}.{key}", findings)
        return
    if isinstance(value, (list, tuple)):
        for index, sub in enumerate(value):
            _walk_args(sub, f"{location}[{index}]", findings)


def _check_action(action: Any, index: int, findings: List[Dict[str, Any]]) -> None:
    location = f"action[{index}]"
    if not isinstance(action, list) or not action or not isinstance(action[0], str):
        # The validator covers structural problems; the linter only adds
        # advisory findings for well-formed inputs.
        return
    name = action[0]

    if name in _LEGACY_NAMES:
        findings.append({
            "rule": "legacy_name",
            "severity": "warning",
            "message": f"{name!r} is a legacy alias; prefer {_LEGACY_NAMES[name]!r}",
            "location": location,
        })

    if name in _DANGEROUS_SCRIPT_COMMANDS:
        findings.append({
            "rule": "arbitrary_script",
            "severity": "warning",
            "message": f"{name!r} runs arbitrary script; gate with WR_set_allow_arbitrary_script",
            "location": location,
        })

    if len(action) >= 2 and action[1] == {}:
        findings.append({
            "rule": "empty_kwargs",
            "severity": "info",
            "message": f"{name!r} called with empty {{}}; drop the kwargs slot",
            "location": location,
        })

    for slot_index in range(1, len(action)):
        _walk_args(action[slot_index], f"{location}.args[{slot_index - 1}]", findings)


def _check_duplicates(action_list: List[Any], findings: List[Dict[str, Any]]) -> None:
    """Flag two identical consecutive actions."""
    for index in range(1, len(action_list)):
        if action_list[index] == action_list[index - 1]:
            findings.append({
                "rule": "duplicate_consecutive",
                "severity": "info",
                "message": f"action[{index}] is identical to action[{index - 1}]",
                "location": f"action[{index}]",
            })


def lint_action(data: Any) -> List[Dict[str, Any]]:
    """Walk an action structure and return the findings list."""
    findings: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        action_list = data.get("webdriver_wrapper")
        meta = data.get("meta") or {}
        if not (meta.get("tags") or []):
            findings.append({
                "rule": "missing_tags",
                "severity": "info",
                "message": "no meta.tags declared; tag-based filters won't pick this file up",
                "location": "meta",
            })
    else:
        action_list = data
    if not isinstance(action_list, list):
        return findings
    for index, action in enumerate(action_list):
        _check_action(action, index, findings)
    _check_duplicates(action_list, findings)
    return findings


def lint_action_file(path: str) -> List[Dict[str, Any]]:
    """Read ``path`` (UTF-8 JSON) and lint the contents."""
    file_path = Path(path)
    if not file_path.exists():
        raise ActionLinterError(f"action file not found: {path}")
    try:
        with open(file_path, encoding="utf-8") as action_file:
            data = json.load(action_file)
    except ValueError as error:
        raise ActionLinterError(f"action file not valid JSON: {path}") from error
    web_runner_logger.info(f"lint_action_file: {path}")
    return lint_action(data)


def severity_counts(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    """Aggregate ``{warning: N, info: M}`` for reporting."""
    counts: Dict[str, int] = {"warning": 0, "info": 0}
    for finding in findings:
        sev = finding.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1
    return counts
