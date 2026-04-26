"""
原生 Chrome DevTools Protocol (CDP) 命令直通，給進階情境用。
Pass-through to raw Chrome DevTools Protocol for advanced scenarios that
WebRunner's higher-level helpers don't cover.

注意 / Note:
- CDP 僅 Chromium 系（Chrome / Edge / Chromium）支援；Firefox / WebKit 會丟錯。
  CDP only works on Chromium-family browsers (Chrome / Edge / Chromium);
  calling on Firefox / WebKit raises.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class CDPError(WebRunnerException):
    """Raised when a CDP command cannot be issued."""


# Cached Playwright CDP sessions keyed by ``id(page)`` so we don't open a new
# session for every command on the same page.
_pw_cdp_sessions: Dict[int, Any] = {}


def selenium_cdp(method: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    在當前 Selenium driver 執行 CDP 命令
    Issue a CDP command via the active Selenium driver.
    """
    web_runner_logger.info(f"selenium_cdp: {method}")
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise CDPError("no Selenium driver active")
    if not hasattr(driver, "execute_cdp_cmd"):
        raise CDPError("active driver does not support CDP (non-Chromium browser?)")
    return driver.execute_cdp_cmd(method, params or {})


def playwright_cdp(method: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    在當前 Playwright page 執行 CDP 命令
    Issue a CDP command via the active Playwright page (cached session per page).
    """
    web_runner_logger.info(f"playwright_cdp: {method}")
    page = playwright_wrapper_instance.page
    session_key = id(page)
    session = _pw_cdp_sessions.get(session_key)
    if session is None:
        try:
            session = playwright_wrapper_instance.context.new_cdp_session(page)
        except Exception as error:  # noqa: BLE001 — surface a friendlier error
            raise CDPError(f"failed to open CDP session (Chromium only): {error!r}") from error
        _pw_cdp_sessions[session_key] = session
    return session.send(method, params or {})


def reset_playwright_cdp_sessions() -> None:
    """Drop cached Playwright CDP sessions (e.g. after browser restart)."""
    _pw_cdp_sessions.clear()
