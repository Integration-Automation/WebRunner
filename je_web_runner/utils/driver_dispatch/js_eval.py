"""
Selenium / Playwright JS 執行的共用 dispatch helper。
Many modules (``csp_reporter`` / ``memory_leak`` / ``smart_wait`` /
``shadow_pierce`` / ``state_diff`` / ``form_autofill``) re-implement the
same backend detection: ``execute_script`` for Selenium, ``evaluate``
for Playwright. This module is the single source of truth so changes
land in one place.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException


class DriverDispatchError(WebRunnerException):
    """Raised when the target lacks both Selenium and Playwright surfaces."""


def evaluate_expression(driver: Any, expression: str) -> Any:
    """
    跑一段 JS 表達式，回傳它的值；支援 Selenium 與 Playwright。
    Run a JS expression and return its value. Selenium uses
    ``execute_script("return <expr>;")``, Playwright uses
    ``evaluate("() => <expr>")``.
    """
    if not isinstance(expression, str) or not expression:
        raise DriverDispatchError("expression must be a non-empty string")
    if hasattr(driver, "execute_script"):
        return driver.execute_script(f"return {expression};")
    if hasattr(driver, "evaluate"):
        return driver.evaluate(f"() => {expression}")
    raise DriverDispatchError(
        "driver has neither execute_script nor evaluate"
    )


def run_script(driver: Any, body: str, *args: Any) -> Any:
    """
    跑一段完整的 JS 腳本（已含 ``return`` / IIFE），可帶位置參數。
    Run a JS body verbatim with optional positional args. Selenium passes
    args via ``arguments[N]``; Playwright accepts a single argument so
    multiple ``args`` are bundled into a list.
    """
    if not isinstance(body, str) or not body:
        raise DriverDispatchError("body must be a non-empty string")
    if hasattr(driver, "execute_script"):
        return driver.execute_script(body, *args)
    if hasattr(driver, "evaluate"):
        if not args:
            return driver.evaluate(body)
        if len(args) == 1:
            return driver.evaluate(body, args[0])
        return driver.evaluate(body, list(args))
    raise DriverDispatchError(
        "driver has neither execute_script nor evaluate"
    )
