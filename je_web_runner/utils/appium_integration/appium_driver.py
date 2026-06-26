"""
Appium 整合：在 Selenium wrapper 上掛上 Appium WebDriver，重用既有指令。
Thin Appium integration. Constructs an Appium WebDriver via the official
Appium-Python-Client and registers it on ``webdriver_wrapper_instance``
so the existing WR_* commands keep working against a mobile session.

``Appium-Python-Client`` 為軟相依。
``Appium-Python-Client`` is a soft dependency.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class AppiumIntegrationError(WebRunnerException):
    """Raised when Appium-Python-Client is missing or a session cannot start."""


def _require_appium():
    """Return ``(appium.webdriver, AppiumOptions)`` or raise an install hint.

    Appium-Python-Client v3 removed the ``desired_capabilities`` kwarg, so the
    caller builds an ``AppiumOptions`` from the capability dict instead.
    """
    try:
        from appium import webdriver  # type: ignore[import-not-found]
        from appium.options.common import AppiumOptions  # type: ignore[import-not-found]
        return webdriver, AppiumOptions
    except ImportError as error:
        raise AppiumIntegrationError(
            "Appium-Python-Client is not installed. "
            "Install with: pip install Appium-Python-Client"
        ) from error


def start_appium_session(
    server_url: str,
    capabilities: dict[str, Any],
    register: bool = True,
) -> Any:
    """
    建立 Appium WebDriver 並註冊到 ``webdriver_wrapper_instance``
    Build an Appium WebDriver and (optionally) register it on the WebRunner
    Selenium wrapper so the rest of the action set works against the
    mobile session.
    """
    web_runner_logger.info(f"start_appium_session: {server_url}")
    if not isinstance(server_url, str) or not (
        server_url.startswith(("http://", "https://"))  # NOSONAR — scheme allow-list, not an outbound HTTP call
    ):
        raise AppiumIntegrationError(f"server_url must be http(s): {server_url!r}")
    if not isinstance(capabilities, dict) or not capabilities:
        raise AppiumIntegrationError("capabilities must be a non-empty dict")
    appium_webdriver, appium_options_cls = _require_appium()
    options = appium_options_cls()
    options.load_capabilities(capabilities)
    driver = appium_webdriver.Remote(command_executor=server_url, options=options)
    if register:
        webdriver_wrapper_instance.current_webdriver = driver
    return driver


def quit_appium_session() -> None:
    """Quit whatever driver is currently registered on the WebRunner wrapper."""
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        return
    try:
        driver.quit()
    finally:
        webdriver_wrapper_instance.current_webdriver = None


def build_android_caps(
    app: str,
    device_name: str = "Android Emulator",
    platform_version: str = "13",
    automation_name: str = "UiAutomator2",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience: build a capabilities dict for Android."""
    caps: dict[str, Any] = {
        "platformName": "Android",
        "appium:platformVersion": platform_version,
        "appium:deviceName": device_name,
        "appium:app": app,
        "appium:automationName": automation_name,
    }
    if extra:
        caps.update(extra)
    return caps


def build_ios_caps(
    app: str,
    device_name: str = "iPhone 15",
    platform_version: str = "17",
    automation_name: str = "XCUITest",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    caps: dict[str, Any] = {
        "platformName": "iOS",
        "appium:platformVersion": platform_version,
        "appium:deviceName": device_name,
        "appium:app": app,
        "appium:automationName": automation_name,
    }
    if extra:
        caps.update(extra)
    return caps
