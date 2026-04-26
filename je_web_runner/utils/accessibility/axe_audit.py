"""
axe-core 注入與稽核工具，輸出當前頁面違反可訪問性規則的清單。
Axe-core injection helper that runs an accessibility audit on the current
page and returns the standard axe results dict (``violations``, ``passes``,
``incomplete`` …).

axe-core 本身不打包進 WebRunner；使用者需自備 ``axe.min.js`` 並透過
``load_axe_source(path)`` 讀進 Python 端。這樣避免重新發行第三方授權程式碼，
也讓使用者選擇要釘哪個版本。
The axe-core JS is **not** bundled here. Provide your own ``axe.min.js``
(downloaded once from npm / CDN) and load it via ``load_axe_source(path)``.
This keeps third-party code out of the repository and lets callers pin the
version they care about.
"""
from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class AccessibilityError(WebRunnerException):
    """Raised when an a11y audit cannot run."""


def load_axe_source(path: str) -> str:
    """讀取本地 axe-core JS 原始碼檔案 / Read a local axe-core source file."""
    file_path = Path(path)
    if not file_path.exists():
        raise AccessibilityError(f"axe source not found: {path}")
    return file_path.read_text(encoding="utf-8")


def _selenium_driver():
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise AccessibilityError("no Selenium driver active")
    return driver


def selenium_run_audit(
    axe_source: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    在當前 Selenium 頁面執行 axe.run，回傳結果 dict
    Run ``axe.run`` on the current Selenium page and return the result dict.

    使用 ``execute_async_script`` 處理 axe 回傳的 Promise。
    Handles axe's Promise return via ``execute_async_script``.
    """
    web_runner_logger.info("selenium_run_audit")
    driver = _selenium_driver()
    driver.execute_script(axe_source)
    options_json = _json.dumps(options) if options else "null"
    script = (
        "var done = arguments[arguments.length - 1];"
        f"var opts = {options_json};"
        "axe.run(document, opts || {}, function(err, results) {"
        "  done({error: err ? String(err) : null, results: results});"
        "});"
    )
    payload = driver.execute_async_script(script)
    if payload and payload.get("error"):
        raise AccessibilityError(f"axe run failed: {payload['error']}")
    return payload.get("results") if payload else {}


def playwright_run_audit(
    axe_source: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    在當前 Playwright 頁面執行 axe.run，回傳結果 dict
    Run ``axe.run`` on the current Playwright page.
    """
    web_runner_logger.info("playwright_run_audit")
    page = playwright_wrapper_instance.page
    page.add_script_tag(content=axe_source)
    return page.evaluate(
        "async (opts) => await axe.run(document, opts || {})",
        options or {},
    )


def summarise_violations(results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    將 axe 結果壓縮成只含 ``id`` / ``impact`` / ``help`` / ``nodes`` 數量的清單
    Compress the axe results into a thin list of {id, impact, help, nodes}.
    """
    if not isinstance(results, dict):
        return []
    summary: List[Dict[str, Any]] = []
    for violation in results.get("violations", []) or []:
        summary.append({
            "id": violation.get("id"),
            "impact": violation.get("impact"),
            "help": violation.get("help"),
            "nodes": len(violation.get("nodes", []) or []),
        })
    return summary
