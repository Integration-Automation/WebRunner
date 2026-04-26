"""
網路節流預設集：在 CDP 上模擬 3G / Fast 3G / 4G / WiFi / Offline 等情境。
Network throttling presets via CDP. Wraps ``Network.emulateNetworkConditions``
on both Selenium and Playwright Chromium drivers so弱網路測試可以一行切換。
"""
from __future__ import annotations

from typing import Any, Dict

from je_web_runner.utils.cdp.cdp_commands import playwright_cdp, selenium_cdp
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class NetworkEmulationError(WebRunnerException):
    """Raised when an unknown preset is requested."""


# Throughput is in bytes per second; latency is in ms. Numbers based on
# Chrome DevTools' published throttling profiles.
_PRESETS: Dict[str, Dict[str, Any]] = {
    "offline": {
        "offline": True,
        "latency": 0,
        "downloadThroughput": 0,
        "uploadThroughput": 0,
    },
    "slow_3g": {
        "offline": False,
        "latency": 400,
        "downloadThroughput": int(400 * 1024 / 8),
        "uploadThroughput": int(400 * 1024 / 8),
    },
    "fast_3g": {
        "offline": False,
        "latency": 150,
        "downloadThroughput": int(1.6 * 1024 * 1024 / 8),
        "uploadThroughput": int(750 * 1024 / 8),
    },
    "regular_4g": {
        "offline": False,
        "latency": 20,
        "downloadThroughput": int(4 * 1024 * 1024 / 8),
        "uploadThroughput": int(3 * 1024 * 1024 / 8),
    },
    "wifi": {
        "offline": False,
        "latency": 2,
        "downloadThroughput": int(30 * 1024 * 1024 / 8),
        "uploadThroughput": int(15 * 1024 * 1024 / 8),
    },
    "no_throttling": {
        "offline": False,
        "latency": 0,
        "downloadThroughput": -1,
        "uploadThroughput": -1,
    },
}


def list_presets() -> list:
    """Return all registered preset names."""
    return sorted(_PRESETS.keys())


def _params(preset: str) -> Dict[str, Any]:
    if preset not in _PRESETS:
        raise NetworkEmulationError(
            f"unknown network preset {preset!r}; available: {list_presets()}"
        )
    return dict(_PRESETS[preset])


def selenium_emulate_network(preset: str) -> Any:
    """Apply ``preset`` via the active Selenium driver's CDP channel."""
    web_runner_logger.info(f"selenium_emulate_network: {preset}")
    return selenium_cdp("Network.emulateNetworkConditions", _params(preset))


def selenium_clear_throttling() -> Any:
    """Convenience for the ``no_throttling`` preset."""
    return selenium_emulate_network("no_throttling")


def playwright_emulate_network(preset: str) -> Any:
    """Apply ``preset`` via the active Playwright page's CDP session."""
    web_runner_logger.info(f"playwright_emulate_network: {preset}")
    return playwright_cdp("Network.emulateNetworkConditions", _params(preset))


def playwright_clear_throttling() -> Any:
    return playwright_emulate_network("no_throttling")
