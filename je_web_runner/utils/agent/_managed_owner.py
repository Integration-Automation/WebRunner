"""An isolated wrapper with context hooks installed before any page is constructed."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.agent._managed_guard import ContextGuard
from je_web_runner.utils.agent.browser import _MONITOR
from je_web_runner.utils.smart_wait.smart_wait import _INSTALL_FETCH_HOOK, _INSTALL_HISTORY_HOOK
from je_web_runner.webdriver.playwright_element_wrapper import PlaywrightElementWrapper
from je_web_runner.webdriver.playwright_wrapper import PlaywrightWrapper


class ManagedPlaywrightOwner(PlaywrightWrapper):  # pylint: disable=too-many-ancestors
    """Fresh runtime, browser, context and element state; no global wrapper is reused."""

    # Keep the existing wrapper's mixin hierarchy; duplicating its engine lifecycle would break ownership.

    def __init__(self, guard: ContextGuard) -> None:
        super().__init__(element_wrapper=PlaywrightElementWrapper())
        self._managed_guard = guard

    def _open_context(self, storage_state: Any = None) -> Any:
        context = super()._open_context(storage_state)
        try:
            self._managed_guard.install(context)
            context.add_init_script(_MONITOR + ";" + _INSTALL_FETCH_HOOK + _INSTALL_HISTORY_HOOK)
            return context
        except Exception:
            context.close()
            raise
