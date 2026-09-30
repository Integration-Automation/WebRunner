"""
AutoControl 橋接 / Run AutoControl ``AC_*`` actions from WebRunner.

``je_auto_control`` is optional and imported only inside these functions: importing it
makes the process DPI-aware on Windows and takes about a second, and Jeffrey_RPA imports
this working tree. :func:`ac_available` looks the package up without importing it.

An action that reaches AutoControl already controls the mouse, keyboard and screen, so
the bridge refuses the AutoControl commands that reach further: running programs or
shell commands (``AC_shell_command``, ``AC_execute_process``), loading packages
(``AC_add_package_*``), running action lists or files (``AC_execute_action``,
``AC_execute_files``), handing a model every command (``AC_run_agent``) and calling back
into WebRunner (``AC_web_*``). A refused name is refused anywhere inside the action,
including in a loop body or in a body passed as a JSON string.
"""
from __future__ import annotations

import importlib.util
import re
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

DENIED_COMMANDS = frozenset({
    "AC_shell_command", "AC_execute_process", "AC_execute_action", "AC_execute_files", "AC_run_agent",
})
DENIED_PREFIXES = ("AC_add_package_", "AC_web_")
_AC_NAME = re.compile(r"AC_[A-Za-z0-9_]+")
_HINT = "je_auto_control is not installed; install it with: pip install je_web_runner[autocontrol]"


class AutoControlBridgeError(WebRunnerException):
    """AutoControl is missing, an action is malformed or refused, or an AutoControl command failed."""


def ac_available() -> bool:
    """
    AutoControl 是否已安裝（不 import）
    True when ``je_auto_control`` is installed; it is looked up, not imported.
    """
    try:
        return importlib.util.find_spec("je_auto_control") is not None
    except (ImportError, ValueError):  # a broken install or a half-imported module
        return False


def ac_executor() -> Any:
    """AutoControl's global action executor; imports ``je_auto_control`` on first use."""
    if not ac_available():
        raise AutoControlBridgeError(_HINT)
    from je_auto_control.utils.executor.action_executor import executor
    return executor


def is_denied(name: str) -> bool:
    """True for an AutoControl command the bridge refuses."""
    return name in DENIED_COMMANDS or name.startswith(DENIED_PREFIXES)


def ac_list_commands() -> list[str]:
    """
    列出可經橋接執行的 AutoControl 命令
    Every ``AC_*`` command the installed AutoControl registers, without the refused ones.
    """
    return sorted(name for name in ac_executor().known_commands() if not is_denied(name))


def _denied_names_in(value: Any) -> set[str]:
    """Every refused command name anywhere in ``value``: keys, values, and inside strings."""
    found: set[str] = set()
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            found.update(name for name in _AC_NAME.findall(item) if is_denied(name))
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, (list, tuple)):
            pending.extend(item)
    return found


def _checked(action: Any) -> list:
    if not isinstance(action, list) or not action or not isinstance(action[0], str) \
            or not action[0].startswith("AC_"):
        raise AutoControlBridgeError(f"an AutoControl action is a list that starts with an AC_ name, got {action!r}")
    denied = _denied_names_in(action)
    if denied:
        raise AutoControlBridgeError(f"refused AutoControl commands {sorted(denied)} in {action[0]}")
    return action


def ac_run_actions(actions: list) -> list[Any]:
    """
    依序執行 AutoControl 動作並回傳各自的結果；第一個失敗就拋出
    Run ``actions`` (``[["AC_click_mouse", {...}], ...]``) in order through AutoControl's
    executor and return each action's value. The first failure stops the list and raises
    :class:`AutoControlBridgeError` with AutoControl's error as its cause.
    """
    if not isinstance(actions, list) or not actions:
        raise AutoControlBridgeError("actions must be a non-empty list of AutoControl actions")
    checked = [_checked(action) for action in actions]
    executor = ac_executor()
    web_runner_logger.info(f"autocontrol bridge: {[action[0] for action in checked]}")
    try:
        record = executor.execute_action(checked, raise_on_error=True)
    except Exception as error:  # AutoControl's own error types; re-raised as one WebRunner error
        raise AutoControlBridgeError(f"AutoControl action failed: {error!r}") from error
    return list(record.values())


def ac_run(action: list) -> Any:
    """
    執行一個 AutoControl 動作並回傳結果
    Run one AutoControl action (``["AC_write", {"write_string": "hi"}]``) and return its value.
    """
    return ac_run_actions([action])[0]
