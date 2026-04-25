"""
瀏覽器端 Storage 操作命令：local/session storage 與 IndexedDB 清除。
Browser-side storage helpers: localStorage / sessionStorage CRUD plus
IndexedDB clear. Built on top of the active driver's script-execution API,
so they work without backend-specific shims.
"""
from __future__ import annotations

from typing import Any, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class StorageError(WebRunnerException):
    """Raised when a storage command cannot proceed."""


def _selenium_evaluate(script: str, *args) -> Any:
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise StorageError("no Selenium driver active")
    return driver.execute_script(script, *args)


def _playwright_evaluate(expression: str, arg: Any = None) -> Any:
    if arg is None:
        return playwright_wrapper_instance.page.evaluate(expression)
    return playwright_wrapper_instance.page.evaluate(expression, arg)


# ----- Selenium -----------------------------------------------------------

def selenium_local_storage_set(key: str, value: str) -> None:
    web_runner_logger.info(f"local_storage_set: {key}")
    _selenium_evaluate("window.localStorage.setItem(arguments[0], arguments[1]);", key, value)


def selenium_local_storage_get(key: str) -> Optional[str]:
    return _selenium_evaluate("return window.localStorage.getItem(arguments[0]);", key)


def selenium_local_storage_remove(key: str) -> None:
    _selenium_evaluate("window.localStorage.removeItem(arguments[0]);", key)


def selenium_local_storage_clear() -> None:
    _selenium_evaluate("window.localStorage.clear();")


def selenium_local_storage_all() -> dict:
    script = (
        "var out = {};"
        "for (var i = 0; i < window.localStorage.length; i++) {"
        "  var k = window.localStorage.key(i);"
        "  out[k] = window.localStorage.getItem(k);"
        "} return out;"
    )
    return _selenium_evaluate(script) or {}


def selenium_session_storage_set(key: str, value: str) -> None:
    _selenium_evaluate("window.sessionStorage.setItem(arguments[0], arguments[1]);", key, value)


def selenium_session_storage_get(key: str) -> Optional[str]:
    return _selenium_evaluate("return window.sessionStorage.getItem(arguments[0]);", key)


def selenium_session_storage_clear() -> None:
    _selenium_evaluate("window.sessionStorage.clear();")


def selenium_indexed_db_drop(db_name: str) -> None:
    """Drop an IndexedDB database by name. Best-effort (Promise resolution skipped)."""
    _selenium_evaluate(
        "try { window.indexedDB.deleteDatabase(arguments[0]); } catch (e) {}",
        db_name,
    )


# ----- Playwright ---------------------------------------------------------

def playwright_local_storage_set(key: str, value: str) -> None:
    web_runner_logger.info(f"playwright local_storage_set: {key}")
    _playwright_evaluate(
        "kv => window.localStorage.setItem(kv[0], kv[1])",
        [key, value],
    )


def playwright_local_storage_get(key: str) -> Optional[str]:
    return _playwright_evaluate("k => window.localStorage.getItem(k)", key)


def playwright_local_storage_remove(key: str) -> None:
    _playwright_evaluate("k => window.localStorage.removeItem(k)", key)


def playwright_local_storage_clear() -> None:
    _playwright_evaluate("() => window.localStorage.clear()")


def playwright_local_storage_all() -> dict:
    expression = (
        "() => { var out = {}; "
        "for (var i = 0; i < window.localStorage.length; i++) {"
        "  var k = window.localStorage.key(i);"
        "  out[k] = window.localStorage.getItem(k);"
        "} return out; }"
    )
    return _playwright_evaluate(expression) or {}


def playwright_session_storage_set(key: str, value: str) -> None:
    _playwright_evaluate(
        "kv => window.sessionStorage.setItem(kv[0], kv[1])",
        [key, value],
    )


def playwright_session_storage_get(key: str) -> Optional[str]:
    return _playwright_evaluate("k => window.sessionStorage.getItem(k)", key)


def playwright_session_storage_clear() -> None:
    _playwright_evaluate("() => window.sessionStorage.clear()")


def playwright_indexed_db_drop(db_name: str) -> None:
    _playwright_evaluate(
        "name => { try { indexedDB.deleteDatabase(name); } catch (e) {} }",
        db_name,
    )
