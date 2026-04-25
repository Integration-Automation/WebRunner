"""
自我修復定位器：當主要 TestObject 找不到元素時，依序嘗試已註冊的備援。
Self-healing locator: when a TestObject lookup misses, fall back through a
registered list of (strategy, value) pairs and log which one matched.

支援 Selenium 與 Playwright 兩個 backend。
Both Selenium and Playwright backends are supported.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from selenium.webdriver.common.by import By

from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_object.test_object_class import TestObject
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import (
    test_object_record,
)
from je_web_runner.webdriver.playwright_element_wrapper import playwright_element_wrapper
from je_web_runner.webdriver.playwright_locator import test_object_to_selector
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class HealingError(WebRunnerException):
    """Raised when no primary or fallback locator matches."""


class HealingRegistry:
    """In-memory store of fallback locators keyed by element name."""

    def __init__(self) -> None:
        self._fallbacks: Dict[str, List[Tuple[str, str]]] = {}

    def register(self, name: str, fallbacks: List[Tuple[str, str]]) -> None:
        """
        登錄某元素名稱的備援定位器
        Register an ordered list of (strategy, value) fallbacks for ``name``.
        """
        self._fallbacks[name] = list(fallbacks)

    def append(self, name: str, strategy: str, value: str) -> None:
        """Append a single fallback entry."""
        self._fallbacks.setdefault(name, []).append((strategy, value))

    def get(self, name: str) -> List[Tuple[str, str]]:
        return list(self._fallbacks.get(name, []))

    def clear(self) -> None:
        self._fallbacks = {}


healing_registry = HealingRegistry()


def _candidates(name: str) -> List[Tuple[str, str]]:
    """Primary TestObject (if recorded) followed by registered fallbacks."""
    candidates: List[Tuple[str, str]] = []
    primary: Optional[TestObject] = test_object_record.test_object_record_dict.get(name)
    if primary is not None:
        candidates.append((primary.test_object_type, primary.test_object_name))
    candidates.extend(healing_registry.get(name))
    return candidates


def _by_for(strategy: str):
    """Map a strategy string to the Selenium ``By`` constant."""
    attr = (strategy or "").upper()
    if not hasattr(By, attr):
        raise HealingError(f"unsupported strategy for Selenium: {strategy!r}")
    return getattr(By, attr)


def find_with_healing_selenium(name: str):
    """
    依序嘗試 primary + fallback locator，回傳第一個命中的 WebElement
    Try the primary TestObject and registered fallbacks in order; the first
    match is captured on the Selenium element wrapper and returned.
    """
    if webdriver_wrapper_instance.current_webdriver is None:
        raise HealingError("no Selenium driver active")
    candidates = _candidates(name)
    if not candidates:
        raise HealingError(f"no primary or fallback locator for {name!r}")
    last_error: Optional[Exception] = None
    for strategy, value in candidates:
        try:
            element = webdriver_wrapper_instance.current_webdriver.find_element(
                _by_for(strategy), value
            )
            web_runner_logger.info(
                f"healing(selenium): {name!r} matched via {strategy}={value!r}"
            )
            web_element_wrapper.current_web_element = element
            return element
        except Exception as error:  # noqa: BLE001 — fall through to next candidate
            last_error = error
    raise HealingError(
        f"no candidate matched for {name!r}; last error: {last_error!r}"
    )


def find_with_healing_playwright(name: str):
    """
    Playwright 版自我修復定位
    Self-healing find on the active Playwright page.
    """
    candidates = _candidates(name)
    if not candidates:
        raise HealingError(f"no primary or fallback locator for {name!r}")
    last_error: Optional[Exception] = None
    for strategy, value in candidates:
        probe = TestObject.__new__(TestObject)
        probe.test_object_name = value
        probe.test_object_type = strategy
        try:
            selector = test_object_to_selector(probe)
            element = playwright_wrapper_instance.page.query_selector(selector)
            if element is None:
                last_error = HealingError(f"{strategy}={value!r} returned no element")
                continue
            web_runner_logger.info(
                f"healing(playwright): {name!r} matched via {strategy}={value!r}"
            )
            playwright_element_wrapper.current_element = element
            return element
        except Exception as error:  # noqa: BLE001 — try the next candidate
            last_error = error
    raise HealingError(
        f"no Playwright candidate matched for {name!r}; last error: {last_error!r}"
    )


def register_fallback(name: str, strategy: str, value: str) -> None:
    """Public helper for use as a WR_* command."""
    healing_registry.append(name, strategy, value)


def register_fallbacks(name: str, fallbacks: List[Any]) -> None:
    """
    Public helper for use as a WR_* command.

    ``fallbacks`` accepts a list of ``[strategy, value]`` pairs (lists or
    tuples) so it round-trips through JSON cleanly.
    """
    pairs = [(item[0], item[1]) for item in fallbacks]
    healing_registry.register(name, pairs)


def clear_fallbacks() -> None:
    healing_registry.clear()
