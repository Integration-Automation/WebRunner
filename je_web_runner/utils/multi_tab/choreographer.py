"""
多 tab 連動腳本：跨 window handles 串連動作（如：A tab 複製連結 → B tab 開啟驗證）。
Multi-tab choreographer over Selenium ``window_handles``. Each tab gets a
named alias so action JSON can refer to "primary" / "side-channel" instead
of opaque handle ids.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class MultiTabError(WebRunnerException):
    """Raised when a tab alias is unknown or driver does not support windows."""


@dataclass
class TabHandle:
    alias: str
    handle: str


@dataclass
class TabChoreographer:
    """Track and switch between named browser tabs."""

    tabs: Dict[str, TabHandle] = field(default_factory=dict)

    def register_current(self, driver: Any, alias: str) -> TabHandle:
        if not hasattr(driver, "current_window_handle"):
            raise MultiTabError("driver does not expose current_window_handle")
        handle = driver.current_window_handle
        tab = TabHandle(alias=alias, handle=handle)
        self.tabs[alias] = tab
        return tab

    def open_new(self, driver: Any, alias: str, url: Optional[str] = None) -> TabHandle:
        """Open a fresh blank tab and register it under ``alias``."""
        if not hasattr(driver, "switch_to") or not hasattr(driver, "window_handles"):
            raise MultiTabError("driver does not expose window_handles / switch_to")
        before = set(driver.window_handles)
        driver.switch_to.new_window("tab")
        new_handles = [h for h in driver.window_handles if h not in before]
        if not new_handles:
            raise MultiTabError("driver did not surface a new window handle")
        new_handle = new_handles[0]
        driver.switch_to.window(new_handle)
        if url is not None and hasattr(driver, "get"):
            driver.get(url)
        return self._register(alias, new_handle)

    def switch_to(self, driver: Any, alias: str) -> TabHandle:
        if alias not in self.tabs:
            raise MultiTabError(f"unknown tab alias: {alias!r}")
        if not hasattr(driver, "switch_to"):
            raise MultiTabError("driver does not expose switch_to")
        tab = self.tabs[alias]
        driver.switch_to.window(tab.handle)
        web_runner_logger.info(f"switched to tab {alias!r}")
        return tab

    def close(self, driver: Any, alias: str) -> None:
        tab = self.tabs.pop(alias, None)
        if tab is None:
            raise MultiTabError(f"unknown tab alias: {alias!r}")
        driver.switch_to.window(tab.handle)
        driver.close()

    def aliases(self) -> List[str]:
        return sorted(self.tabs.keys())

    def with_tab(
        self,
        driver: Any,
        alias: str,
        action: Callable[[Any], Any],
    ) -> Any:
        """Run ``action(driver)`` while the given alias is active."""
        previous = getattr(driver, "current_window_handle", None)
        self.switch_to(driver, alias)
        try:
            return action(driver)
        finally:
            if previous is not None and previous in driver.window_handles:
                driver.switch_to.window(previous)

    def _register(self, alias: str, handle: str) -> TabHandle:
        tab = TabHandle(alias=alias, handle=handle)
        self.tabs[alias] = tab
        return tab
