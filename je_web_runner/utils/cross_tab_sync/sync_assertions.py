"""
跨 tab / context 狀態同步測試:BroadcastChannel / localStorage /
SharedWorker / Window.postMessage,以多個 Playwright page 驗證
更新在其他 tab 即時反映。

Common assertions:

* :func:`wait_for_storage` — wait for ``localStorage[key]`` on a tab to
  match ``expected`` (with optional JSON parsing).
* :func:`broadcast_message` — send a structured BroadcastChannel message
  from one tab, optionally on a named channel.
* :func:`assert_state_propagates` — write storage / broadcast on the
  source tab, expect each listener tab to observe it within ``timeout``.
* :func:`collect_broadcast_messages` — install a recorder on a tab so
  later assertions can pop messages it received.

All helpers operate on Playwright ``Page`` objects (no direct dep on
Selenium — the cross-tab story works far better with Playwright's
multi-page model).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

_PAGE_IS_NONE_MSG = "page is None"


class CrossTabSyncError(WebRunnerException):
    """Raised when an expected propagation does not happen in time."""


# ---------- localStorage / sessionStorage --------------------------------

def set_storage_value(
    page: Any,
    key: str,
    value: Any,
    *,
    storage: str = "localStorage",
) -> None:
    """
    在 page 上設一個 storage 值。
    ``value`` is JSON-serialised so callers can hand in dicts/lists.
    """
    _ensure_storage_name(storage)
    if page is None:
        raise CrossTabSyncError(_PAGE_IS_NONE_MSG)
    payload = json.dumps(value)
    script = (
        f"({{ key, raw }}) => window.{storage}.setItem(key, raw)"
    )
    try:
        page.evaluate(script, {"key": key, "raw": payload})
    except Exception as error:  # noqa: BLE001 — playwright surfaces many
        raise CrossTabSyncError(f"set_storage_value failed: {error!r}") from error
    web_runner_logger.info(f"set_storage_value: {storage}[{key}] = {payload[:80]}")


def get_storage_value(
    page: Any,
    key: str,
    *,
    storage: str = "localStorage",
    json_parse: bool = True,
) -> Any:
    """Read ``storage[key]`` from the page. Returns ``None`` when absent."""
    _ensure_storage_name(storage)
    if page is None:
        raise CrossTabSyncError(_PAGE_IS_NONE_MSG)
    script = f"(key) => window.{storage}.getItem(key)"
    try:
        raw = page.evaluate(script, key)
    except Exception as error:  # noqa: BLE001
        raise CrossTabSyncError(f"get_storage_value failed: {error!r}") from error
    if raw is None:
        return None
    if not json_parse:
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


def wait_for_storage(
    page: Any,
    key: str,
    expected: Any,
    *,
    storage: str = "localStorage",
    timeout: float = 5.0,
    poll_interval: float = 0.1,
    sleep_fn: Callable[[float], None] = time.sleep,
    time_fn: Callable[[], float] = time.time,
) -> Any:
    """
    輪詢直到 ``storage[key]`` 等於 ``expected`` 或 timeout。
    Comparison is JSON-aware: a dict ``expected`` will match a JSON-encoded
    value stored as a string. Returns the matched value.
    """
    _validate_timeout(timeout, poll_interval)
    start = time_fn()
    while True:
        current = get_storage_value(page, key, storage=storage, json_parse=True)
        if current == expected:
            return current
        if time_fn() - start >= timeout:
            raise CrossTabSyncError(
                f"timeout: {storage}[{key}] = {current!r}, expected {expected!r}"
            )
        sleep_fn(poll_interval)


# ---------- BroadcastChannel ---------------------------------------------

def install_broadcast_recorder(page: Any, channel_name: str) -> None:
    """
    Hook 一個 ``window.__wr_broadcast_log__`` 蒐集所有 BroadcastChannel 訊息。
    Idempotent — installing twice replaces the previous recorder.
    """
    if page is None:
        raise CrossTabSyncError(_PAGE_IS_NONE_MSG)
    if not channel_name:
        raise CrossTabSyncError("channel_name is required")
    script = """
        (channelName) => {
            if (window.__wr_broadcast_channels__ &&
                window.__wr_broadcast_channels__[channelName]) {
                window.__wr_broadcast_channels__[channelName].close();
            }
            window.__wr_broadcast_log__ = window.__wr_broadcast_log__ || {};
            window.__wr_broadcast_log__[channelName] = [];
            window.__wr_broadcast_channels__ = window.__wr_broadcast_channels__ || {};
            const ch = new BroadcastChannel(channelName);
            ch.onmessage = (ev) => {
                window.__wr_broadcast_log__[channelName].push({
                    data: ev.data,
                    receivedAt: Date.now(),
                });
            };
            window.__wr_broadcast_channels__[channelName] = ch;
            return true;
        }
    """
    try:
        page.evaluate(script, channel_name)
    except Exception as error:  # noqa: BLE001
        raise CrossTabSyncError(
            f"install_broadcast_recorder failed: {error!r}"
        ) from error


def broadcast_message(page: Any, channel_name: str, data: Any) -> None:
    """Post one message to ``channel_name`` from ``page``."""
    if page is None:
        raise CrossTabSyncError(_PAGE_IS_NONE_MSG)
    if not channel_name:
        raise CrossTabSyncError("channel_name is required")
    script = """
        ({ channelName, payload }) => {
            const ch = new BroadcastChannel(channelName);
            ch.postMessage(payload);
            ch.close();
            return true;
        }
    """
    try:
        page.evaluate(script, {"channelName": channel_name, "payload": data})
    except Exception as error:  # noqa: BLE001
        raise CrossTabSyncError(f"broadcast_message failed: {error!r}") from error
    web_runner_logger.info(
        f"broadcast_message: channel={channel_name!r}"
    )


def collect_broadcast_messages(
    page: Any,
    channel_name: str,
) -> List[Dict[str, Any]]:
    """Return everything the recorder on ``page`` has captured for ``channel_name``."""
    if page is None:
        raise CrossTabSyncError(_PAGE_IS_NONE_MSG)
    script = """
        (channelName) => {
            if (!window.__wr_broadcast_log__) return [];
            return window.__wr_broadcast_log__[channelName] || [];
        }
    """
    try:
        result = page.evaluate(script, channel_name)
    except Exception as error:  # noqa: BLE001
        raise CrossTabSyncError(
            f"collect_broadcast_messages failed: {error!r}"
        ) from error
    if not isinstance(result, list):
        return []
    return result


def wait_for_broadcast(
    page: Any,
    channel_name: str,
    matcher: Callable[[Any], bool],
    *,
    timeout: float = 5.0,
    poll_interval: float = 0.1,
    sleep_fn: Callable[[float], None] = time.sleep,
    time_fn: Callable[[], float] = time.time,
) -> Dict[str, Any]:
    """
    輪詢 recorder 直到出現一條符合 ``matcher`` 的訊息。
    Returns the matching message entry (with ``data`` and ``receivedAt``).
    """
    _validate_timeout(timeout, poll_interval)
    start = time_fn()
    while True:
        messages = collect_broadcast_messages(page, channel_name)
        for entry in messages:
            data = entry.get("data") if isinstance(entry, dict) else None
            try:
                hit = matcher(data)
            except Exception:  # noqa: BLE001 — matcher should be cheap
                hit = False
            if hit:
                return entry
        if time_fn() - start >= timeout:
            raise CrossTabSyncError(
                f"timeout: no broadcast on {channel_name!r} matched within {timeout}s"
            )
        sleep_fn(poll_interval)


# ---------- assert_state_propagates --------------------------------------

@dataclass
class PropagationResult:
    """Outcome of one :func:`assert_state_propagates` call."""

    propagated_to: List[int] = field(default_factory=list)
    elapsed_seconds: float = 0.0


def assert_state_propagates(
    source_page: Any,
    listener_pages: Sequence[Any],
    *,
    key: str,
    value: Any,
    storage: str = "localStorage",
    timeout: float = 5.0,
    poll_interval: float = 0.1,
    sleep_fn: Callable[[float], None] = time.sleep,
    time_fn: Callable[[], float] = time.time,
) -> PropagationResult:
    """
    在 source_page 設 storage,要求每個 listener_pages 在 timeout 內看到。
    Raises if any listener does not observe the value before ``timeout``.
    Returns ``PropagationResult`` listing the listener indices observed
    plus the total elapsed wait time.
    """
    if source_page is None:
        raise CrossTabSyncError("source_page is None")
    if not listener_pages:
        raise CrossTabSyncError("at least one listener_pages entry is required")
    set_storage_value(source_page, key, value, storage=storage)
    start = time_fn()
    seen = [False] * len(listener_pages)
    while True:
        for idx, page in enumerate(listener_pages):
            if seen[idx]:
                continue
            current = get_storage_value(page, key, storage=storage, json_parse=True)
            if current == value:
                seen[idx] = True
        if all(seen):
            return PropagationResult(
                propagated_to=[i for i, s in enumerate(seen) if s],
                elapsed_seconds=time_fn() - start,
            )
        if time_fn() - start >= timeout:
            missing = [i for i, s in enumerate(seen) if not s]
            raise CrossTabSyncError(
                f"timeout: storage {key!r} did not propagate to tabs {missing} "
                f"after {timeout}s"
            )
        sleep_fn(poll_interval)


# ---------- helpers ------------------------------------------------------

_ALLOWED_STORAGE = {"localStorage", "sessionStorage"}


def _ensure_storage_name(name: str) -> None:
    if name not in _ALLOWED_STORAGE:
        raise CrossTabSyncError(
            f"storage must be one of {sorted(_ALLOWED_STORAGE)}, got {name!r}"
        )


def _validate_timeout(timeout: float, poll_interval: float) -> None:
    if timeout <= 0:
        raise CrossTabSyncError("timeout must be positive")
    if poll_interval <= 0:
        raise CrossTabSyncError("poll_interval must be positive")


# ---------- post-message helper ------------------------------------------

def post_message_to_page(
    page: Any,
    data: Any,
    *,
    target_origin: str = "*",
) -> None:
    """``window.postMessage(data, target_origin)`` on the page's main window."""
    if page is None:
        raise CrossTabSyncError(_PAGE_IS_NONE_MSG)
    script = "({ payload, origin }) => window.postMessage(payload, origin)"
    try:
        page.evaluate(script, {"payload": data, "origin": target_origin})
    except Exception as error:  # noqa: BLE001
        raise CrossTabSyncError(f"post_message_to_page failed: {error!r}") from error
