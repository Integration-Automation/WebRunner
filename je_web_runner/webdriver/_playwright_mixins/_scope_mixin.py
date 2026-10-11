"""目前的 frame、依 role / 文字找元素、對話框處理 / Frame scope, role and text lookup, dialog policy."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver._playwright_mixins._common import PlaywrightBackendError, recorded

_LOOKUPS = frozenset({"role", "text", "label", "placeholder", "alt_text", "title", "test_id"})
_DIALOG_ACTIONS = frozenset({"accept", "dismiss", "default"})


class _ScopeMixin:
    """Where the next selector-based commands act, and what happens to JavaScript dialogs.

    Like Selenium's frame switching, :meth:`switch_to_frame` makes the selector
    commands (click, fill, find, wait_for_selector, evaluate …) act inside an iframe
    until :meth:`switch_to_main_frame`, a navigation or a page switch. Mouse, keyboard,
    screenshots and navigation always act on the page.
    """

    @property
    def _target(self) -> Any:
        """The current frame, or the page when no frame is selected."""
        return self._frame if self._frame is not None else self.page

    # ----- frames ------------------------------------------------------

    @recorded()
    def switch_to_frame(self, selectors: str | list[str]) -> None:
        """
        切進 iframe（可給一串 selector 逐層進入）
        Select the iframe matching ``selectors`` (a selector, or a list for nested
        iframes), relative to the current frame; later selector commands act in it.
        """
        chain = [selectors] if isinstance(selectors, str) else list(selectors)
        target = self._target
        for selector in chain:
            element = target.query_selector(selector)
            frame = element.content_frame() if element is not None else None
            if frame is None:
                raise PlaywrightBackendError(f"no iframe matches {selector!r}")
            target = frame
        self._frame = target

    @recorded()
    def switch_to_parent_frame(self) -> None:
        """Select the parent of the current frame (the page for a top-level iframe)."""
        if self._frame is None:
            return
        parent = self._frame.parent_frame
        self._frame = None if parent is None or parent is self.page.main_frame else parent

    @recorded()
    def switch_to_main_frame(self) -> None:
        """Act on the page again."""
        self._frame = None

    # ----- role / text lookup ---------------------------------------------

    @recorded()
    def find_by(self, by: str, value: str, wait: bool = True, **options: Any) -> Any:
        """
        以 Playwright 的使用者導向定位方式找元素
        Find elements the way a user would: ``by`` is ``role``, ``text``, ``label``,
        ``placeholder``, ``alt_text``, ``title`` or ``test_id`` (Playwright's
        ``get_by_*``); ``options`` go to it (``name`` and ``exact`` for a role …). The
        first match becomes the current element for the ``WR_pw_element_*`` commands.
        With ``wait`` it waits (default timeout) for a match to be attached first.
        """
        if by not in _LOOKUPS:
            raise PlaywrightBackendError(f"find_by: unknown lookup {by!r}; use one of {sorted(_LOOKUPS)}")
        locator = getattr(self._target, f"get_by_{by}")(value, **options)
        if wait:
            locator.first.wait_for(state="attached")
        handles = list(locator.element_handles())
        self.element_wrapper.current_element_list = handles
        self.element_wrapper.current_element = handles[0] if handles else None
        return handles[0] if handles else None

    # ----- dialogs -----------------------------------------------------

    @recorded()
    def set_dialog_policy(self, action: str = "accept", prompt_text: str | None = None) -> None:
        """
        設定 alert / confirm / prompt 對話框的處理方式
        Decide what happens to JavaScript dialogs on every page from now on:
        ``accept`` (with ``prompt_text`` for a prompt), ``dismiss``, or ``default``
        (Playwright's own behaviour: dismiss). The last dialog is kept for
        :meth:`last_dialog`.
        """
        if action not in _DIALOG_ACTIONS:
            raise PlaywrightBackendError(f"dialog action must be one of {sorted(_DIALOG_ACTIONS)}, not {action!r}")
        self._dialog_policy = (action, prompt_text)
        for page in self._pages:
            self._watch_dialogs(page)

    def last_dialog(self) -> dict[str, Any] | None:
        """``{type, message, default_value, action}`` of the last dialog handled, or None."""
        return self._last_dialog

    def _watch_dialogs(self, page: Any) -> None:
        if self._dialog_policy is None or any(watched is page for watched in self._dialog_pages):
            return
        page.on("dialog", self._on_dialog)
        self._dialog_pages.append(page)

    def _on_dialog(self, dialog: Any) -> None:
        action, prompt_text = self._dialog_policy or ("default", None)
        self._last_dialog = {
            "type": dialog.type, "message": dialog.message,
            "default_value": dialog.default_value, "action": action,
        }
        web_runner_logger.info(f"playwright dialog {dialog.type}: {dialog.message!r} -> {action}")
        if action == "accept":
            if prompt_text is None:
                dialog.accept()
            else:
                dialog.accept(prompt_text)
        else:
            dialog.dismiss()
