"""
透過注入 JS 監聽器的瀏覽器操作錄製器，將使用者點擊與輸入反向轉成 WR_* action JSON。
Browser action recorder via injected JS listeners; converts captured user
events back into WR_* action JSON consumable by the executor.

設計重點 / Design notes:
- 不使用 CDP，靠 ``execute_script`` 注入靜態腳本，因此 Chrome / Firefox / Edge
  都能用，並避免動態執行使用者輸入（CLAUDE.md 安全規則）。
- 所有 JS 都是常數字串，事件資料以 JSON 格式從瀏覽器拉回 Python 端。
- 翻譯結果使用 ``CSS_SELECTOR`` 定位，後續可由人工微調。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.json.json_file.json_file import write_action_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class RecorderError(WebRunnerException):
    """Raised when the recorder cannot install or read events."""


_RECORDER_JS = r"""
(function() {
  if (window.__wr_recorder_installed) { return; }
  window.__wr_recorder_installed = true;
  window.__wr_events = [];

  function cssPath(el) {
    if (!el || el.nodeType !== 1) return null;
    if (el.id) return '#' + el.id;
    if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
    var parts = [];
    while (el && el.nodeType === 1 && el.tagName.toLowerCase() !== 'html') {
      var idx = 1;
      var sib = el;
      while ((sib = sib.previousElementSibling)) {
        if (sib.tagName === el.tagName) idx++;
      }
      parts.unshift(el.tagName.toLowerCase() + ':nth-of-type(' + idx + ')');
      el = el.parentElement;
    }
    return parts.join(' > ');
  }

  function looksSensitive(target, value) {
    if (target.type === 'password') return true;
    var label = ((target.name || target.id || target.autocomplete || '') + '').toLowerCase();
    if (/(card[\-_]?number|cvv|cvc|ssn|secret|token|api[\-_]?key|otp|passcode)/.test(label)) {
      return true;
    }
    var digits = (value || '').replace(/[\s-]/g, '');
    if (/^[0-9]{13,19}$/.test(digits)) return true;
    return false;
  }

  document.addEventListener('click', function(ev) {
    var sel = cssPath(ev.target);
    if (sel) window.__wr_events.push({type: 'click', selector: sel, time: Date.now()});
  }, true);

  document.addEventListener('change', function(ev) {
    var sel = cssPath(ev.target);
    if (!sel) return;
    var value = String(ev.target.value || '');
    var masked = looksSensitive(ev.target, value);
    if (masked) value = '***MASKED***';
    window.__wr_events.push({
      type: 'input', selector: sel, value: value, masked: masked, time: Date.now()
    });
  }, true);
})();
"""

_DRAIN_JS = (
    "var events = window.__wr_events || []; "
    "window.__wr_events = []; "
    "return events;"
)

_RESET_JS = "window.__wr_recorder_installed = false; window.__wr_events = [];"


_SENSITIVE_NAME_RE = re.compile(
    r"(password|card[-_]?number|cvv|cvc|ssn|secret|token|api[-_]?key|otp|passcode)",
    re.IGNORECASE,
)
_LONG_DIGIT_RE = re.compile(r"^[0-9]{13,19}$")


def _looks_sensitive(selector: str, value: str) -> bool:
    if not isinstance(value, str):
        return False
    if _SENSITIVE_NAME_RE.search(selector or ""):
        return True
    digits = re.sub(r"[\s-]", "", value)
    return bool(_LONG_DIGIT_RE.match(digits))


def mask_sensitive_events(events: Iterable[dict]) -> List[dict]:
    """
    在 Python 端再做一次遮罩，保險起見
    Defensive Python-side masking pass; mainly useful when consuming raw
    events that bypassed the JS-side masking (e.g. loaded from disk).
    """
    masked: List[dict] = []
    for event in events:
        copy = dict(event)
        if copy.get("type") == "input" and not copy.get("masked"):
            value = copy.get("value", "")
            if _looks_sensitive(copy.get("selector", ""), value):
                copy["value"] = "***MASKED***"
                copy["masked"] = True
        masked.append(copy)
    return masked


def _resolve_driver(driver_or_wrapper) -> object:
    """Accept either a raw WebDriver or a WebDriverWrapper exposing current_webdriver."""
    if hasattr(driver_or_wrapper, "current_webdriver") and driver_or_wrapper.current_webdriver:
        return driver_or_wrapper.current_webdriver
    if hasattr(driver_or_wrapper, "execute_script"):
        return driver_or_wrapper
    raise RecorderError("driver has no execute_script and no current_webdriver")


def start_recording(driver_or_wrapper) -> None:
    """
    在當前頁面注入錄製器腳本。再次呼叫可在新頁面重新注入（idempotent）。
    Inject the recorder script into the current page (idempotent).
    """
    web_runner_logger.info("recorder: start_recording")
    driver = _resolve_driver(driver_or_wrapper)
    driver.execute_script(_RECORDER_JS)


def pull_events(driver_or_wrapper) -> List[dict]:
    """
    從瀏覽器拉回累積事件並清空緩衝
    Drain accumulated events from the browser side and clear the buffer.
    """
    driver = _resolve_driver(driver_or_wrapper)
    events = driver.execute_script(_DRAIN_JS) or []
    if not isinstance(events, list):
        raise RecorderError(f"unexpected events payload type: {type(events).__name__}")
    return events


def stop_recording(driver_or_wrapper) -> None:
    """
    停用錄製器並清掉狀態（不會移除 listeners，重整頁面即可）
    Disable the recorder flag and clear buffered events. Listeners persist on
    the current document; navigate or reload to drop them.
    """
    web_runner_logger.info("recorder: stop_recording")
    driver = _resolve_driver(driver_or_wrapper)
    driver.execute_script(_RESET_JS)


def _click_to_actions(event: dict, name_index: int) -> List[list]:
    test_object_name = event["selector"]
    return [
        [
            "WR_SaveTestObject",
            {"test_object_name": test_object_name, "object_type": "CSS_SELECTOR"},
        ],
        ["WR_find_element", {"element_name": test_object_name}],
        ["WR_left_click", {"element_name": test_object_name}],
    ]


def _input_to_actions(event: dict, name_index: int) -> List[list]:
    test_object_name = event["selector"]
    value = event.get("value", "")
    return [
        [
            "WR_SaveTestObject",
            {"test_object_name": test_object_name, "object_type": "CSS_SELECTOR"},
        ],
        ["WR_find_element", {"element_name": test_object_name}],
        ["WR_input_to_element", {"input_value": value}],
    ]


def events_to_actions(events: Iterable[dict]) -> List[list]:
    """
    將事件清單翻譯成 WR_* action 序列
    Translate captured events into a WR_* action list.

    未支援的事件類型會被忽略並寫入日誌。
    Unsupported event types are skipped and logged.
    """
    actions: List[list] = []
    handlers = {"click": _click_to_actions, "input": _input_to_actions}
    for index, event in enumerate(events):
        event_type = event.get("type")
        handler = handlers.get(event_type)
        if handler is None:
            web_runner_logger.warning(f"recorder: unsupported event type {event_type!r}")
            continue
        actions.extend(handler(event, index))
    return actions


def save_recording(
    driver_or_wrapper,
    output_path: str,
    raw_events_path: Optional[str] = None,
) -> str:
    """
    便捷函式：拉回事件、轉成 actions、寫出 JSON
    Convenience: drain events, translate to actions, write JSON.

    :param driver_or_wrapper: 已注入錄製器的 driver 或 wrapper
                               driver / wrapper that has been started
    :param output_path: action JSON 輸出路徑 / action JSON output path
    :param raw_events_path: 可選的原始事件輸出路徑（除錯用）
                             optional path for the raw event log (debugging)
    :return: 寫出的 action JSON 路徑 / path written
    """
    events = pull_events(driver_or_wrapper)
    if raw_events_path:
        Path(raw_events_path).parent.mkdir(parents=True, exist_ok=True)
        with open(raw_events_path, "w", encoding="utf-8") as raw_out:
            json.dump(events, raw_out, indent=2)
    actions = events_to_actions(events)
    write_action_json(output_path, actions)
    return output_path
