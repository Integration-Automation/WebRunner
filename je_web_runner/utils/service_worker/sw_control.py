"""
Service Worker 與 Cache Storage 控制：避免 SW 干擾測試。
Service Worker / Cache Storage controls so caches and registered SWs do not
poison test runs.
"""
from __future__ import annotations

from typing import List

from je_web_runner.utils.cdp.cdp_commands import playwright_cdp, selenium_cdp
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class ServiceWorkerError(WebRunnerException):
    """Raised when an SW / cache command cannot proceed."""


_UNREGISTER_JS = (
    "var done = arguments[arguments.length - 1];"
    "if (!('serviceWorker' in navigator)) { done([]); return; }"
    "navigator.serviceWorker.getRegistrations().then(function(regs) {"
    "  return Promise.all(regs.map(function(r) { return r.unregister(); })).then("
    "    function(results) { done(results); }"
    "  );"
    "}).catch(function(e) { done({error: String(e)}); });"
)

_CACHES_CLEAR_JS = (
    "var done = arguments[arguments.length - 1];"
    "if (!('caches' in window)) { done([]); return; }"
    "caches.keys().then(function(keys) {"
    "  return Promise.all(keys.map(function(k) { return caches.delete(k); })).then("
    "    function() { done(keys); }"
    "  );"
    "}).catch(function(e) { done({error: String(e)}); });"
)


def selenium_unregister_service_workers() -> List[bool]:
    """
    解除註冊當前頁面所有 Service Worker
    Unregister all service workers on the current page.
    """
    web_runner_logger.info("selenium_unregister_service_workers")
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise ServiceWorkerError("no Selenium driver active")
    return driver.execute_async_script(_UNREGISTER_JS) or []


def selenium_clear_caches() -> List[str]:
    """
    清空 Cache Storage
    Clear all entries from the browser's Cache Storage.
    """
    web_runner_logger.info("selenium_clear_caches")
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise ServiceWorkerError("no Selenium driver active")
    return driver.execute_async_script(_CACHES_CLEAR_JS) or []


def selenium_bypass_service_worker(bypass: bool = True) -> None:
    """
    透過 CDP 設定 ServiceWorker bypass（僅 Chromium 系）
    Bypass the service worker via CDP (Chromium-family browsers only).
    """
    selenium_cdp("Network.setBypassServiceWorker", {"bypass": bool(bypass)})


def playwright_unregister_service_workers() -> List[bool]:
    web_runner_logger.info("playwright_unregister_service_workers")
    page = playwright_wrapper_instance.page
    return page.evaluate(
        "async () => {"
        "  if (!('serviceWorker' in navigator)) return [];"
        "  const regs = await navigator.serviceWorker.getRegistrations();"
        "  return Promise.all(regs.map(r => r.unregister()));"
        "}"
    ) or []


def playwright_clear_caches() -> List[str]:
    web_runner_logger.info("playwright_clear_caches")
    page = playwright_wrapper_instance.page
    return page.evaluate(
        "async () => {"
        "  if (!('caches' in window)) return [];"
        "  const keys = await caches.keys();"
        "  await Promise.all(keys.map(k => caches.delete(k)));"
        "  return keys;"
        "}"
    ) or []


def playwright_bypass_service_worker(bypass: bool = True) -> None:
    """Bypass the service worker via CDP on the active Playwright page."""
    playwright_cdp("Network.setBypassServiceWorker", {"bypass": bool(bypass)})
