"""
把 HTTP action 餵進 Locust 跑壓力測試。
Replay HTTP API actions through Locust for load testing.

``locust`` 為軟相依：使用此功能時才匯入。
Locust is a soft dependency — imported lazily so the rest of WebRunner
runs without it.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class LoadTestError(WebRunnerException):
    """Raised when Locust is unavailable or a load run fails."""


def _require_locust():
    try:
        from locust import HttpUser, between, task  # type: ignore[import-not-found]
        from locust.env import Environment  # type: ignore[import-not-found]
        return HttpUser, between, task, Environment
    except ImportError as error:
        raise LoadTestError(
            "Locust is not installed. Install with: pip install locust"
        ) from error


def _build_task(action: Dict[str, Any]) -> Callable:
    """Turn an action dict into a Locust task method."""
    method = (action.get("method") or "GET").upper()
    path = action.get("path") or "/"
    name = action.get("name") or f"{method} {path}"
    json_body = action.get("json_body")
    headers = action.get("headers")
    params = action.get("params")

    def run_task(self):
        self.client.request(
            method,
            path,
            name=name,
            json=json_body,
            headers=headers,
            params=params,
        )

    run_task.__name__ = (action.get("name") or "task").replace(" ", "_")
    return run_task


def build_http_user_class(
    actions: List[Dict[str, Any]],
    wait_min: float = 1.0,
    wait_max: float = 3.0,
) -> type:
    """
    依 actions 動態建立一個 ``HttpUser`` 子類別
    Build an HttpUser subclass with one ``@task(weight)`` per action.

    Each action dict supports: ``name``, ``method``, ``path``, ``weight``,
    ``json_body``, ``headers``, ``params``.
    """
    http_user_cls, between, task, _environment_cls = _require_locust()
    attrs: Dict[str, Any] = {"wait_time": between(wait_min, wait_max)}
    for index, action in enumerate(actions):
        weight = int(action.get("weight", 1))
        attrs[f"task_{index}"] = task(weight)(_build_task(action))
    # Honour Locust's custom metaclass instead of forcing the built-in ``type``.
    user_metaclass = type(http_user_cls)
    return user_metaclass("WebRunnerHttpUser", (http_user_cls,), attrs)


def run_locust(
    host: str,
    actions: List[Dict[str, Any]],
    num_users: int = 10,
    spawn_rate: float = 2.0,
    run_seconds: float = 60.0,
    wait_min: float = 1.0,
    wait_max: float = 3.0,
) -> Dict[str, Any]:
    """
    無頭模式跑 Locust 並回傳統計
    Run Locust headlessly against ``host`` with the given actions and return
    a stats summary (total / failures / median / p95 / rps per endpoint).

    :param run_seconds: 總時長 / total run time in seconds
    :return: dict with ``total`` and ``per_endpoint``
    """
    if not isinstance(host, str) or not (host.startswith("http://") or host.startswith("https://")):
        raise LoadTestError(f"host must be http(s): {host!r}")
    web_runner_logger.info(f"run_locust host={host} users={num_users} run_seconds={run_seconds}")
    _http_user_cls, _between, _task, environment_cls = _require_locust()
    user_class = build_http_user_class(actions, wait_min=wait_min, wait_max=wait_max)
    user_class.host = host

    env = environment_cls(user_classes=[user_class])
    runner = env.create_local_runner()
    runner.start(num_users, spawn_rate=spawn_rate)
    try:
        time.sleep(max(float(run_seconds), 0.0))
    finally:
        runner.stop()

    return _summarise_stats(env.stats)


def _summarise_stats(stats: Any) -> Dict[str, Any]:
    """Pull a small dict summary out of Locust's stats object."""
    per_endpoint: List[Dict[str, Any]] = []
    for entry in getattr(stats, "entries", {}).values():
        per_endpoint.append({
            "name": entry.name,
            "method": entry.method,
            "num_requests": int(entry.num_requests),
            "num_failures": int(entry.num_failures),
            "median_response_time": float(entry.median_response_time),
            "avg_response_time": float(entry.avg_response_time),
            "current_rps": float(entry.current_rps),
        })
    total = stats.total
    return {
        "total": {
            "num_requests": int(total.num_requests),
            "num_failures": int(total.num_failures),
            "median_response_time": float(total.median_response_time),
            "avg_response_time": float(total.avg_response_time),
        },
        "per_endpoint": per_endpoint,
    }
