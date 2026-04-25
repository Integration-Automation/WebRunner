"""
A/B 模式：同一份 action 對兩個環境各跑一次，回傳逐步比對結果。
A/B mode: run the same action set against two environments and return a
step-level comparison. Useful for verifying parity between dev and staging,
or before/after migrations.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance


def _default_runner(action_data):
    # Imported lazily to avoid a circular import: this module is wired into
    # the executor's event_dict, but execute_action lives in that same module.
    from je_web_runner.utils.executor.action_executor import execute_action
    return execute_action(action_data)


class ABRunError(WebRunnerException):
    """Raised when an A/B run cannot proceed."""


_NO_EXCEPTION = "None"


def _snapshot_records() -> List[Dict[str, Any]]:
    """Take a deep-ish copy of the current records buffer."""
    return [dict(record) for record in test_record_instance.test_record_list]


def _run_one_side(
    label: str,
    setup: Optional[Callable[[], Any]],
    action_data: Any,
    runner: Callable[[Any], Any],
) -> List[Dict[str, Any]]:
    web_runner_logger.info(f"ab_run side={label}")
    test_record_instance.clean_record()
    if setup is not None:
        setup()
    runner(action_data)
    return _snapshot_records()


def _step_status(record: Dict[str, Any]) -> str:
    return "failed" if record.get("program_exception", _NO_EXCEPTION) != _NO_EXCEPTION else "passed"


def diff_records(
    records_a: List[Dict[str, Any]],
    records_b: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    比對兩側的 record 序列；回傳每步的差異
    Compare two record sequences step-by-step and return summary + diffs.
    """
    summary = {
        "len_a": len(records_a),
        "len_b": len(records_b),
        "length_match": len(records_a) == len(records_b),
    }
    differences: List[Dict[str, Any]] = []
    pairs = zip(records_a, records_b)
    for index, (left, right) in enumerate(pairs):
        left_status = _step_status(left)
        right_status = _step_status(right)
        if left_status != right_status or left.get("function_name") != right.get("function_name"):
            differences.append({
                "step": index,
                "a": {
                    "function_name": left.get("function_name"),
                    "status": left_status,
                    "exception": left.get("program_exception"),
                },
                "b": {
                    "function_name": right.get("function_name"),
                    "status": right_status,
                    "exception": right.get("program_exception"),
                },
            })
    return {"summary": summary, "differences": differences}


def run_ab(
    action_data: Any,
    setup_a: Optional[Callable[[], Any]] = None,
    setup_b: Optional[Callable[[], Any]] = None,
    runner: Optional[Callable[[Any], Any]] = None,
) -> Dict[str, Any]:
    """
    對兩個環境跑同一份 action 並回傳比對結果
    Run ``action_data`` against two environments. ``setup_a`` / ``setup_b``
    are zero-arg callables invoked just before each run (typical use:
    ``lambda: load_env("dev")``).

    :return: ``{records_a, records_b, diff}``
    """
    actual_runner = runner if runner is not None else _default_runner
    records_a = _run_one_side("A", setup_a, action_data, actual_runner)
    records_b = _run_one_side("B", setup_b, action_data, actual_runner)
    return {
        "records_a": records_a,
        "records_b": records_b,
        "diff": diff_records(records_a, records_b),
    }
