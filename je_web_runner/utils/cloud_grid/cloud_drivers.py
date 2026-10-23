"""Generic Remote WebDriver connector for a self-hosted Selenium Grid."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class CloudGridError(WebRunnerException):
    """Invalid generic Grid configuration."""


def start_remote_driver(
    hub_url: str,
    capabilities: dict[str, Any],
    register: bool = True,
) -> WebDriver:
    """
    啟動 Remote WebDriver；預設將其註冊到 ``webdriver_wrapper_instance``
    Start a Remote WebDriver and (optionally) register it on the WebRunner
    Selenium wrapper so the rest of the action set works against it.
    """
    target = urlsplit(hub_url)
    if target.scheme not in {"http", "https"} or not target.hostname:
        raise CloudGridError("hub_url must be an absolute HTTP(S) URL")
    if target.username is not None or target.password is not None:
        raise CloudGridError("hub_url must not contain credentials")
    if not isinstance(capabilities, dict):
        raise CloudGridError("capabilities must be an object")
    web_runner_logger.info("start_remote_driver")
    options = webdriver.ChromeOptions()
    for key, value in capabilities.items():
        options.set_capability(key, value)
    driver = webdriver.Remote(command_executor=hub_url, options=options)
    if register:
        # set_active_driver (not a bare current_webdriver assignment) so the
        # wrapper's ActionChains bind to this remote driver.
        webdriver_wrapper_instance.set_active_driver(driver)
    return driver

