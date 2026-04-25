"""
失敗分類器：把錯誤訊息與 ledger 歷史對映到 transient / flaky / environment / real。
Heuristic failure classifier so triage can prioritise the real bugs.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.run_ledger.flaky import flaky_paths


class ClassifierError(WebRunnerException):
    """Raised when classification fails."""


_TRANSIENT_PATTERNS = [
    re.compile(r"\bConnectionRefused"),
    re.compile(r"\bConnectionReset"),
    re.compile(r"\bTimeoutError\b", re.IGNORECASE),
    re.compile(r"\bWebDriverException"),
    re.compile(r"\bStale\s*Element\s*Reference", re.IGNORECASE),
    re.compile(r"\b502 Bad Gateway\b"),
    re.compile(r"\b503 Service Unavailable\b"),
    re.compile(r"\b504 Gateway Timeout\b"),
]

_ENVIRONMENT_PATTERNS = [
    re.compile(r"\bENOSPC\b"),
    re.compile(r"No space left on device"),
    re.compile(r"MemoryError"),
    re.compile(r"chromedriver.*not.*found", re.IGNORECASE),
    re.compile(r"geckodriver.*not.*found", re.IGNORECASE),
    re.compile(r"DNS lookup failed"),
]


def classify_error(error_repr: str) -> Optional[str]:
    """
    依錯誤字串嘗試判定 transient / environment；無法判定回傳 None
    Try to bucket an error repr into ``transient`` / ``environment``;
    return ``None`` when neither pattern matches.
    """
    if not isinstance(error_repr, str) or not error_repr:
        return None
    for pattern in _TRANSIENT_PATTERNS:
        if pattern.search(error_repr):
            return "transient"
    for pattern in _ENVIRONMENT_PATTERNS:
        if pattern.search(error_repr):
            return "environment"
    return None


def classify(error_repr: str, ledger_path: Optional[str] = None,
             file_path: Optional[str] = None) -> str:
    """
    綜合錯誤字串與 ledger 歷史回傳分類
    Combine error text + ledger history to bucket a single failure into
    transient / environment / flaky / real.
    """
    web_runner_logger.info("classify failure")
    error_bucket = classify_error(error_repr)
    if error_bucket is not None:
        return error_bucket
    if ledger_path and file_path:
        if file_path in flaky_paths(ledger_path):
            return "flaky"
    return "real"


def classify_failures(
    failures: Iterable[Dict[str, Any]],
    ledger_path: Optional[str] = None,
) -> Dict[str, str]:
    """
    對 ``[{function_name, exception, file_path?}, ...]`` 各分類
    Map each failure entry to a category.
    """
    result: Dict[str, str] = {}
    for failure in failures:
        key = str(failure.get("file_path") or failure.get("function_name") or len(result))
        result[key] = classify(
            failure.get("exception", ""),
            ledger_path=ledger_path,
            file_path=failure.get("file_path"),
        )
    return result
