"""分頁、導航、逾時、找元素 / Pages, navigation, timeouts and element lookup."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver._playwright_mixins._common import recorded
from je_web_runner.webdriver._playwright_mixins._common import PlaywrightBackendError, record
from je_web_runner.webdriver.playwright_locator import selector_for_recorded_name


class _PageMixin:
    """分頁切換、URL 導航、預設逾時、依 selector 或 TestObject 找元素。

    Page (tab) management, URL navigation, default timeouts, and element lookup
    by selector or recorded TestObject name.
    """

    @recorded()
    def new_page(self) -> int:
        """Open a new page in the current context; returns its index."""
        page = self.context.new_page()
        self._track_page(page)
        self._page_index = self._pages.index(page)
        return self._page_index

    def _track_page(self, page: Any) -> None:
        """
        記住 context 開啟的每個分頁（包含網站自己開的 popup）
        Remember a page the context opened, including popups and ``window.open``
        pages the site opens itself; forget it again when it closes.
        """
        if any(known is page for known in self._pages):
            return
        self._pages.append(page)
        page.on("close", self._forget_page)

    def _forget_page(self, page: Any) -> None:
        index = next((i for i, known in enumerate(self._pages) if known is page), None)
        if index is None:
            return
        del self._pages[index]
        if not self._pages:
            self._page_index = -1
        elif index < self._page_index:
            self._page_index -= 1
        else:
            self._page_index = min(self._page_index, len(self._pages) - 1)

    @recorded()
    def switch_to_page(self, index: int) -> None:
        if index < 0 or index >= len(self._pages):
            raise PlaywrightBackendError(f"page index {index} out of range")
        self._page_index = index

    @recorded()
    def close_page(self, index: int | None = None) -> None:
        target_index = self._page_index if index is None else index
        if target_index < 0 or target_index >= len(self._pages):
            raise PlaywrightBackendError(f"page index {target_index} out of range")
        page = self._pages[target_index]
        page.close()
        self._forget_page(page)

    def page_count(self) -> int:
        return len(self._pages)

    # ----- navigation --------------------------------------------------

    def to_url(self, url: str, **goto_options: Any) -> None:
        web_runner_logger.info(f"playwright to_url: {url}")
        params = {"url": url}
        try:
            self.page.goto(url, **goto_options)
            record("to_url", params, None)
        except Exception as error:
            web_runner_logger.error(f"playwright to_url failed: {error!r}")
            record("to_url", params, error)

    @recorded()
    def forward(self) -> None:
        self.page.go_forward()

    @recorded()
    def back(self) -> None:
        self.page.go_back()

    @recorded()
    def refresh(self) -> None:
        self.page.reload()

    def url(self) -> str:
        return self.page.url

    def title(self) -> str:
        return self.page.title()

    def content(self) -> str:
        return self.page.content()

    @recorded()
    def set_default_timeout(self, timeout_ms: float) -> None:
        self.page.set_default_timeout(timeout_ms)

    @recorded()
    def set_default_navigation_timeout(self, timeout_ms: float) -> None:
        self.page.set_default_navigation_timeout(timeout_ms)

    # ----- finding -----------------------------------------------------

    def find_element(self, selector: str):
        web_runner_logger.info(f"playwright find_element: {selector}")
        return self.page.query_selector(selector)

    def find_elements(self, selector: str) -> list[Any]:
        web_runner_logger.info(f"playwright find_elements: {selector}")
        return self.page.query_selector_all(selector)

    def find_element_with_test_object_record(self, element_name: str):
        """
        Resolve ``element_name`` from ``test_object_record`` and capture the
        first matching element on ``element_wrapper``.
        """
        selector = selector_for_recorded_name(element_name)
        element = self.page.query_selector(selector)
        self.element_wrapper.current_element = element
        return element

    def find_elements_with_test_object_record(self, element_name: str):
        selector = selector_for_recorded_name(element_name)
        elements = self.page.query_selector_all(selector)
        self.element_wrapper.current_element_list = list(elements)
        if elements:
            self.element_wrapper.current_element = elements[0]
        return elements
