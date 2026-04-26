"""
基於 ``requests`` 的 HTTP 測試命令，供 action JSON 與瀏覽器流程混用。
``requests``-backed HTTP commands so action JSON can mix API calls with
browser automation in the same script.

安全考量 / Security:
- 不關閉憑證驗證；CLAUDE.md 禁止 ``verify=False``。
  TLS verification stays on; CLAUDE.md disallows ``verify=False``.
- 預設逾時 30 秒；可透過參數調整，避免無限等待。
  Default timeout is 30s to avoid hanging calls; override per request.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import requests

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class HttpAssertionError(WebRunnerException):
    """Raised when an HTTP assertion against the last response fails."""


_DEFAULT_TIMEOUT = 30
_state: Dict[str, Any] = {"last_response": None}


def _allowed_url(url: str) -> str:
    if not isinstance(url, str) or not url:
        raise WebRunnerException("HTTP URL must be a non-empty string")
    if not (url.startswith("http://") or url.startswith("https://")):  # NOSONAR — scheme allow-list, not an outbound HTTP call
        raise WebRunnerException(f"HTTP URL must start with http:// or https://: {url!r}")
    return url


def _summarise(response: requests.Response) -> Dict[str, Any]:
    """Return a JSON-friendly dict capturing the response state we care about."""
    summary: Dict[str, Any] = {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "elapsed_ms": int(response.elapsed.total_seconds() * 1000),
        "text": response.text,
    }
    try:
        summary["json"] = response.json()
    except ValueError:
        summary["json"] = None
    _state["last_response"] = summary
    return summary


def http_request(
    method: str,
    url: str,
    timeout: int = _DEFAULT_TIMEOUT,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Any = None,
    data: Any = None,
    **request_kwargs: Any,
) -> Dict[str, Any]:
    """
    通用 HTTP 請求；其他 ``http_*`` 命令皆呼叫此函式
    Generic HTTP entry point; the verb-specific helpers delegate here.
    """
    safe_url = _allowed_url(url)
    web_runner_logger.info(f"http_request {method.upper()} {safe_url}")
    response = requests.request(
        method.upper(),
        safe_url,
        timeout=timeout,
        headers=headers,
        params=params,
        json=json_body,
        data=data,
        **request_kwargs,
    )
    return _summarise(response)


def http_get(url: str, **kwargs: Any) -> Dict[str, Any]:
    return http_request("GET", url, **kwargs)


def http_post(url: str, **kwargs: Any) -> Dict[str, Any]:
    return http_request("POST", url, **kwargs)


def http_put(url: str, **kwargs: Any) -> Dict[str, Any]:
    return http_request("PUT", url, **kwargs)


def http_patch(url: str, **kwargs: Any) -> Dict[str, Any]:
    return http_request("PATCH", url, **kwargs)


def http_delete(url: str, **kwargs: Any) -> Dict[str, Any]:
    return http_request("DELETE", url, **kwargs)


def get_last_response() -> Optional[Dict[str, Any]]:
    """Return the most recent ``_summarise`` output (or ``None``)."""
    return _state["last_response"]


def http_assert_status(expected: int) -> None:
    """
    斷言上一次回應的 HTTP 狀態碼
    Assert the last response's status code matches ``expected``.
    """
    last = _state["last_response"]
    if last is None:
        raise HttpAssertionError("no HTTP response recorded yet")
    if last["status_code"] != int(expected):
        raise HttpAssertionError(
            f"expected status {expected}, got {last['status_code']}"
        )


def http_assert_json_contains(key: str, expected: Any) -> None:
    """
    斷言上一次 JSON 回應於 ``key`` 的值等於 ``expected``
    Assert ``last_response.json[key] == expected``. Raises if no JSON body.
    """
    last = _state["last_response"]
    if last is None:
        raise HttpAssertionError("no HTTP response recorded yet")
    body = last.get("json")
    if not isinstance(body, dict):
        raise HttpAssertionError("last response has no JSON body to inspect")
    if key not in body:
        raise HttpAssertionError(f"key {key!r} not in JSON body: {sorted(body.keys())}")
    if body[key] != expected:
        raise HttpAssertionError(
            f"json[{key!r}] expected {expected!r}, got {body[key]!r}"
        )


def reset_state() -> None:
    """Clear the recorded last_response (mainly for tests)."""
    _state["last_response"] = None
