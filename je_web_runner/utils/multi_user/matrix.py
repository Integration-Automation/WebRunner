"""
Multi-user matrix：同一份 action 對 N 位使用者 / 角色逐一執行並比對。
Run the same action set for each of N user contexts (login cookies, JWT,
custom headers) and produce a per-user record snapshot plus pairwise
status diffs.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance


class MultiUserError(WebRunnerException):
    """Raised when matrix runs cannot proceed."""


_NO_EXCEPTION = "None"


def _step_status(record: Dict[str, Any]) -> str:
    return "failed" if record.get("program_exception", _NO_EXCEPTION) != _NO_EXCEPTION else "passed"


def _capture_records() -> List[Dict[str, Any]]:
    return [dict(record) for record in test_record_instance.test_record_list]


def _default_runner(action_data):
    from je_web_runner.utils.executor.action_executor import execute_action
    return execute_action(action_data)


def run_for_users(
    action_data: Any,
    user_setups: List[Tuple[str, Optional[Callable[[], Any]]]],
    runner: Optional[Callable[[Any], Any]] = None,
) -> Dict[str, Any]:
    """
    對每位使用者執行一次 ``action_data``，回傳記錄與差異
    Run ``action_data`` once per user context. ``user_setups`` is a list of
    ``(name, setup_callable)`` pairs; ``setup_callable`` may be ``None`` if
    no per-user setup is required (e.g. anonymous baseline).

    :return: dict ``{by_user: {name: records}, diff: [...]}``
    """
    web_runner_logger.info(f"run_for_users: {[name for name, _ in user_setups]}")
    if not user_setups:
        raise MultiUserError("user_setups must not be empty")
    actual_runner = runner if runner is not None else _default_runner

    by_user: Dict[str, List[Dict[str, Any]]] = {}
    for name, setup in user_setups:
        web_runner_logger.info(f"run_for_users user={name}")
        test_record_instance.clean_record()
        if setup is not None:
            setup()
        actual_runner(action_data)
        by_user[name] = _capture_records()

    return {"by_user": by_user, "diff": _build_diff(by_user)}


def _build_diff(by_user: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """For every step index, list users whose status disagrees with the rest."""
    if not by_user:
        return []
    names = list(by_user.keys())
    max_steps = max(len(records) for records in by_user.values())
    diffs: List[Dict[str, Any]] = []
    for step_index in range(max_steps):
        per_user_status: Dict[str, Optional[str]] = {}
        per_user_function: Dict[str, Optional[str]] = {}
        for name in names:
            records = by_user[name]
            if step_index < len(records):
                per_user_status[name] = _step_status(records[step_index])
                per_user_function[name] = records[step_index].get("function_name")
            else:
                per_user_status[name] = None
                per_user_function[name] = None
        # Include ``None`` so length-differences (some users skipped this
        # step entirely) also surface as diffs.
        unique_statuses = set(per_user_status.values())
        unique_functions = set(per_user_function.values())
        if len(unique_statuses) > 1 or len(unique_functions) > 1:
            diffs.append({
                "step": step_index,
                "status": dict(per_user_status),
                "function_name": dict(per_user_function),
            })
    return diffs
