"""同時開多個瀏覽器 / Several Playwright browsers at once, switched by index."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver._playwright_mixins._common import PlaywrightBackendError

# Everything that belongs to one browser session; the Playwright runtime is shared.
_SESSION_FIELDS = (
    "_browser", "_context", "_pages", "_page_index", "_context_options", "_emulation_keys",
    "_fixed_context", "_trace_options", "_init_scripts", "_blocked_urls", "_cache_route",
    "_frame", "_dialog_policy", "_dialog_pages", "_last_dialog",
)


class _SessionsMixin:
    """Several browsers in one wrapper, like Selenium's ``WR_new_driver`` / ``WR_change_index_of_webdriver``.

    Other modules import ``playwright_wrapper_instance`` by name, so the wrapper
    object stays the same: switching saves the current browser's state (browser,
    context, pages, settings, current element) and loads another's. ``_sessions``
    holds one entry per browser; the active entry is ``None`` because its state
    lives on the wrapper itself.
    """

    def _snapshot(self) -> dict[str, Any]:
        state = {name: getattr(self, name) for name in _SESSION_FIELDS}
        state["current_element"] = self.element_wrapper.current_element
        state["current_element_list"] = self.element_wrapper.current_element_list
        return state

    def _restore(self, state: dict[str, Any]) -> None:
        for name in _SESSION_FIELDS:
            setattr(self, name, state[name])
        self.element_wrapper.current_element = state["current_element"]
        self.element_wrapper.current_element_list = state["current_element_list"]

    def _park_active(self) -> None:
        if self._sessions:
            self._sessions[self._session_index] = self._snapshot()

    def browser_count(self) -> int:
        """How many browsers this wrapper holds."""
        return len(self._sessions)

    def new_browser(self, browser: str = "chromium", headless: bool = True, **launch_kwargs: Any) -> int:
        """
        再開一個瀏覽器並切換過去
        Launch another browser (keeping the others open), make it current and return
        its index. Takes the same arguments as ``launch``.
        """
        if self._sessions:
            self._park_active()
            self._reset_state()
            self.element_wrapper.current_element = None
            self.element_wrapper.current_element_list = None
            self._sessions.append(None)
            self._session_index = len(self._sessions) - 1
        self.launch(browser=browser, headless=headless, **launch_kwargs)
        web_runner_logger.info(f"playwright new_browser: {browser} is browser {self._session_index}")
        return self._session_index

    def switch_browser(self, index: int) -> None:
        """Make browser ``index`` (0-based, in opening order) the one commands act on."""
        if not 0 <= index < len(self._sessions):
            raise PlaywrightBackendError(f"browser index {index} out of range (0..{len(self._sessions) - 1})")
        if index == self._session_index:
            return
        self._park_active()
        self._restore(self._sessions[index])
        self._sessions[index] = None
        self._session_index = index

    def close_browser(self) -> None:
        """
        關閉目前的瀏覽器
        Close the current browser and continue with the one before it; closing the
        last one also stops the Playwright runtime.
        """
        self._close_current()
        del self._sessions[self._session_index]
        if not self._sessions:
            self._reset_state()
            self._stop_runtime()
            return
        self._session_index = min(self._session_index, len(self._sessions) - 1)
        self._restore(self._sessions[self._session_index])
        self._sessions[self._session_index] = None

    def _close_current(self) -> None:
        if self._browser is not None:
            self._browser.close()
        elif self._context is not None:
            self._context.close()
