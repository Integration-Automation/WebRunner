"""
TestRail 整合：將每個 case 的 pass/fail 推到指定的 run。
TestRail integration: push case-level pass/fail results into a run.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

import requests
from requests.auth import HTTPBasicAuth

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class TestRailError(WebRunnerException):
    """Raised when a TestRail API call fails."""


_DEFAULT_TIMEOUT = 30
_PASSED, _FAILED = 1, 5  # TestRail status_id values


def _check_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url:
        raise TestRailError("base_url must be a non-empty string")
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        raise TestRailError(f"base_url must be http(s): {base_url!r}")
    return base_url.rstrip("/")


def testrail_send_results(
    base_url: str,
    username: str,
    api_key: str,
    run_id: int,
    results: List[Dict[str, Any]],
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    將結果送到 ``add_results_for_cases/{run_id}``
    Submit results to ``index.php?/api/v2/add_results_for_cases/{run_id}``.

    ``results`` 內每筆需含 ``case_id`` 與 ``status_id``。
    Each entry must include ``case_id`` and ``status_id``.
    """
    web_runner_logger.info(f"testrail_send_results: run_id={run_id} count={len(results)}")
    url = f"{_check_url(base_url)}/index.php?/api/v2/add_results_for_cases/{int(run_id)}"
    response = requests.post(
        url,
        json={"results": results},
        auth=HTTPBasicAuth(username, api_key),
        timeout=timeout,
        headers={"Content-Type": "application/json"},
    )
    if response.status_code >= 400:
        raise TestRailError(f"TestRail returned {response.status_code}: {response.text[:200]}")
    return response.json()


def testrail_results_from_pairs(
    pairs: Iterable[Dict[str, Any]],
    comment_field: str = "comment",
) -> List[Dict[str, Any]]:
    """
    把 ``[{case_id, passed, comment?}]`` 轉成 TestRail status_id 格式
    Helper: turn a list of {case_id, passed, comment?} dicts into the
    payload TestRail expects.
    """
    out: List[Dict[str, Any]] = []
    for pair in pairs:
        case_id = pair.get("case_id")
        if case_id is None:
            continue
        entry: Dict[str, Any] = {
            "case_id": int(case_id),
            "status_id": _PASSED if pair.get("passed") else _FAILED,
        }
        if comment_field in pair:
            entry["comment"] = str(pair[comment_field])
        out.append(entry)
    return out


def testrail_close_run(
    base_url: str,
    username: str,
    api_key: str,
    run_id: int,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    關閉指定的 TestRail run
    Close a TestRail run via ``index.php?/api/v2/close_run/{run_id}``.
    """
    web_runner_logger.info(f"testrail_close_run: run_id={run_id}")
    url = f"{_check_url(base_url)}/index.php?/api/v2/close_run/{int(run_id)}"
    response = requests.post(
        url,
        auth=HTTPBasicAuth(username, api_key),
        timeout=timeout,
        headers={"Content-Type": "application/json"},
    )
    if response.status_code >= 400:
        raise TestRailError(f"TestRail returned {response.status_code}: {response.text[:200]}")
    return response.json()
