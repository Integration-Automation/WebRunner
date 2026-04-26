"""
雲端 Grid 接入：BrowserStack / Sauce Labs / LambdaTest 的 Remote driver 建構器。
Cloud Selenium Grid integrations: build provider-specific capability dicts
and Remote drivers for BrowserStack, Sauce Labs, and LambdaTest.

安全 / Security:
- 認證以參數傳入；不接受寫死、不寫進 log。
  Credentials are passed as arguments only — never hard-coded, never logged.
- 預設 hub URL 為各家公開的官方端點，但呼叫者可以覆蓋。
  Default hub URLs are the providers' public endpoints; callable can override.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Dict, Optional

from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class CloudGridError(WebRunnerException):
    """Raised when a cloud Remote driver cannot be started."""


_DEFAULT_HUBS: Dict[str, str] = {
    "browserstack": "https://hub-cloud.browserstack.com/wd/hub",
    "saucelabs": "https://ondemand.us-west-1.saucelabs.com:443/wd/hub",
    "lambdatest": "https://hub.lambdatest.com/wd/hub",
}


def _hub_url_with_credentials(hub_url: str, username: str, access_key: str) -> str:
    """Inject ``user:key`` into the hub URL's authority."""
    if not username or not access_key:
        raise CloudGridError("username and access_key are required")
    parsed = urllib.parse.urlparse(hub_url)
    if not parsed.scheme or not parsed.netloc:
        raise CloudGridError(f"invalid hub URL: {hub_url!r}")
    encoded_user = urllib.parse.quote(username, safe="")
    encoded_key = urllib.parse.quote(access_key, safe="")
    netloc_no_creds = parsed.netloc.split("@")[-1]
    new_netloc = f"{encoded_user}:{encoded_key}@{netloc_no_creds}"
    return urllib.parse.urlunparse(parsed._replace(netloc=new_netloc))


def build_browserstack_capabilities(
    browser_name: str = "chrome",
    browser_version: str = "latest",
    os_name: str = "Windows",
    os_version: str = "11",
    project: Optional[str] = None,
    build: Optional[str] = None,
    name: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a W3C-style capability dict for BrowserStack."""
    bstack: Dict[str, Any] = {"os": os_name, "osVersion": os_version}
    if project:
        bstack["projectName"] = project
    if build:
        bstack["buildName"] = build
    if name:
        bstack["sessionName"] = name
    caps: Dict[str, Any] = {
        "browserName": browser_name,
        "browserVersion": browser_version,
        "bstack:options": bstack,
    }
    if extra:
        caps.update(extra)
    return caps


def build_saucelabs_capabilities(
    browser_name: str = "chrome",
    browser_version: str = "latest",
    platform_name: str = "Windows 11",
    build: Optional[str] = None,
    name: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sauce: Dict[str, Any] = {}
    if build:
        sauce["build"] = build
    if name:
        sauce["name"] = name
    caps: Dict[str, Any] = {
        "browserName": browser_name,
        "browserVersion": browser_version,
        "platformName": platform_name,
        "sauce:options": sauce,
    }
    if extra:
        caps.update(extra)
    return caps


def build_lambdatest_capabilities(
    browser_name: str = "Chrome",
    browser_version: str = "latest",
    platform_name: str = "Windows 11",
    build: Optional[str] = None,
    name: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    lt: Dict[str, Any] = {}
    if build:
        lt["build"] = build
    if name:
        lt["name"] = name
    caps: Dict[str, Any] = {
        "browserName": browser_name,
        "browserVersion": browser_version,
        "platformName": platform_name,
        "LT:Options": lt,
    }
    if extra:
        caps.update(extra)
    return caps


def start_remote_driver(
    hub_url: str,
    capabilities: Dict[str, Any],
    register: bool = True,
) -> WebDriver:
    """
    啟動 Remote WebDriver；預設將其註冊到 ``webdriver_wrapper_instance``
    Start a Remote WebDriver and (optionally) register it on the WebRunner
    Selenium wrapper so the rest of the action set works against it.
    """
    web_runner_logger.info("start_remote_driver")
    options = webdriver.ChromeOptions()
    for key, value in capabilities.items():
        options.set_capability(key, value)
    driver = webdriver.Remote(command_executor=hub_url, options=options)
    if register:
        webdriver_wrapper_instance.current_webdriver = driver
    return driver


def _connect(provider: str, username: str, access_key: str,
             capabilities: Dict[str, Any], hub_url: Optional[str]) -> WebDriver:
    target_hub = hub_url or _DEFAULT_HUBS[provider]
    return start_remote_driver(_hub_url_with_credentials(target_hub, username, access_key), capabilities)


def connect_browserstack(
    username: str,
    access_key: str,
    capabilities: Optional[Dict[str, Any]] = None,
    hub_url: Optional[str] = None,
) -> WebDriver:
    return _connect(
        "browserstack",
        username,
        access_key,
        capabilities or build_browserstack_capabilities(),
        hub_url,
    )


def connect_saucelabs(
    username: str,
    access_key: str,
    capabilities: Optional[Dict[str, Any]] = None,
    hub_url: Optional[str] = None,
) -> WebDriver:
    return _connect(
        "saucelabs",
        username,
        access_key,
        capabilities or build_saucelabs_capabilities(),
        hub_url,
    )


def connect_lambdatest(
    username: str,
    access_key: str,
    capabilities: Optional[Dict[str, Any]] = None,
    hub_url: Optional[str] = None,
) -> WebDriver:
    return _connect(
        "lambdatest",
        username,
        access_key,
        capabilities or build_lambdatest_capabilities(),
        hub_url,
    )
