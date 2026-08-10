"""
E2E test fixtures.

Set ``WEBRUNNER_E2E_HUB`` to the Selenium Grid URL (default
``http://localhost:4444/wd/hub``). Tests skip cleanly when the hub is
unreachable so the suite stays green on machines without Docker.

Set ``WEBRUNNER_E2E_ORIGIN`` to an http(s) URL the *browser* can load when the
default (the hub's own Grid console) isn't reachable from the node container.

Usage:

    cd docker && docker compose up -d
    WEBRUNNER_E2E_HUB=http://localhost:4444/wd/hub \\
        python -m pytest test/e2e_test/ -m e2e
"""
from __future__ import annotations

import os
import socket
from typing import Iterator
from urllib.parse import urlparse

import pytest


_DEFAULT_HUB = "http://localhost:4444/wd/hub"
# Reachable from *inside* the browser container, not from the test runner:
# both docker-compose.yml and the CI workflow name the hub service
# ``selenium-hub``, which resolves on the network the node shares with it.
_DEFAULT_ORIGIN = "http://selenium-hub:4444/"


def _hub_reachable(hub_url: str, timeout: float = 1.0) -> bool:
    parsed = urlparse(hub_url)
    if not parsed.hostname or not parsed.port:
        return False
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=timeout):
            return True
    except OSError:
        return False


def pytest_configure(config):  # noqa: D401
    config.addinivalue_line(
        "markers", "e2e: real browser end-to-end tests"
    )


@pytest.fixture(scope="session")
def selenium_hub_url() -> str:
    """Return the configured Selenium Grid URL."""
    return os.environ.get("WEBRUNNER_E2E_HUB", _DEFAULT_HUB)


@pytest.fixture(scope="session")
def hub_reachable(selenium_hub_url: str) -> bool:
    """Whether the Selenium hub TCP port answers connections."""
    return _hub_reachable(selenium_hub_url)


@pytest.fixture(scope="session")
def http_origin_url() -> str:
    """Return a real http(s) origin for tests that touch browser storage."""
    return os.environ.get("WEBRUNNER_E2E_ORIGIN", _DEFAULT_ORIGIN)


@pytest.fixture
def storage_origin(chrome_driver, http_origin_url: str) -> str:
    """
    Park the shared driver on an origin where web storage actually works.

    ``data:`` URLs are opaque origins and Chrome answers any ``localStorage``
    access there with "Storage is disabled inside 'data:' URLs", so storage
    tests need a genuine http(s) origin. Skip rather than fail when the
    browser can't reach one — that's an environment gap, not a defect.
    """
    from selenium.common.exceptions import WebDriverException
    try:
        chrome_driver.get(http_origin_url)
        chrome_driver.execute_script("return window.localStorage.length;")
    except WebDriverException as error:
        pytest.skip(f"no usable storage origin at {http_origin_url!r}: {error}")
    return http_origin_url


@pytest.fixture(scope="session")
def chrome_driver(selenium_hub_url: str, hub_reachable: bool) -> Iterator:
    """Real Selenium ChromeDriver pointed at the Grid; skip when no Grid."""
    if not hub_reachable:
        pytest.skip(f"Selenium hub at {selenium_hub_url!r} unreachable")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:  # pragma: no cover - selenium is a soft dep
        pytest.skip("selenium not installed")
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    try:
        driver = webdriver.Remote(
            command_executor=selenium_hub_url,
            options=options,
        )
    except Exception as error:  # pylint: disable=broad-except
        pytest.skip(f"could not start chrome on grid: {error!r}")
    try:
        yield driver
    finally:
        try:
            driver.quit()
        except Exception:  # pylint: disable=broad-except  # nosec B110 — best-effort cleanup
            pass
