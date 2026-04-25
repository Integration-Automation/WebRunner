"""
跑完測試後發送結果摘要到 Slack / 通用 webhook。
Post a run summary to a Slack incoming webhook or any HTTP webhook.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance


class NotifierError(WebRunnerException):
    """Raised when a webhook call cannot proceed or returns an error status."""


_NO_EXCEPTION_MARKER = "None"
_DEFAULT_TIMEOUT = 10


def _check_url(url: str) -> str:
    if not isinstance(url, str) or not url:
        raise NotifierError("webhook URL must be a non-empty string")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise NotifierError(f"webhook URL must be http(s): {url!r}")
    return url


def summarise_run() -> Dict[str, Any]:
    """
    從 ``test_record_instance`` 產生 pass/fail 統計
    Build a {total, passed, failed, failures} summary from the recorded
    actions.
    """
    records = test_record_instance.test_record_list
    failures = [
        {"function_name": r.get("function_name"), "exception": r.get("program_exception")}
        for r in records
        if r.get("program_exception", _NO_EXCEPTION_MARKER) != _NO_EXCEPTION_MARKER
    ]
    passed = len(records) - len(failures)
    return {
        "total": len(records),
        "passed": passed,
        "failed": len(failures),
        "failures": failures,
    }


def notify_webhook(
    url: str,
    payload: Dict[str, Any],
    timeout: int = _DEFAULT_TIMEOUT,
    headers: Optional[Dict[str, str]] = None,
) -> int:
    """
    POST 任意 JSON payload 到 webhook，回傳 HTTP 狀態碼
    POST a JSON payload to ``url`` and return the HTTP status code.
    """
    safe_url = _check_url(url)
    web_runner_logger.info(f"notify_webhook: {safe_url}")
    response = requests.post(safe_url, json=payload, timeout=timeout, headers=headers)
    if response.status_code >= 400:
        raise NotifierError(
            f"webhook responded with {response.status_code}: {response.text[:200]}"
        )
    return response.status_code


def _slack_text(summary: Dict[str, Any], header: str) -> str:
    lines = [
        f"*{header}*",
        f"total: {summary['total']}  passed: {summary['passed']}  failed: {summary['failed']}",
    ]
    if summary["failed"]:
        lines.append("*failures:*")
        for failure in summary["failures"][:10]:
            lines.append(f"• {failure['function_name']}: {failure['exception']}")
        if summary["failed"] > 10:
            lines.append(f"… {summary['failed'] - 10} more")
    return "\n".join(lines)


def notify_slack(
    webhook_url: str,
    summary: Optional[Dict[str, Any]] = None,
    header: str = "WebRunner Run Summary",
) -> int:
    """
    將摘要包成 Slack incoming-webhook 格式並送出
    Wrap a summary into Slack incoming-webhook format and post it.
    """
    final_summary = summary if summary is not None else summarise_run()
    payload = {"text": _slack_text(final_summary, header)}
    return notify_webhook(webhook_url, payload)


def notify_run_summary(webhook_url: str, header: str = "WebRunner Run Summary") -> int:
    """
    一鍵：取摘要 → Slack 格式 → 送出
    One-shot: build run summary, format for Slack, send.
    """
    return notify_slack(webhook_url, summarise_run(), header=header)
