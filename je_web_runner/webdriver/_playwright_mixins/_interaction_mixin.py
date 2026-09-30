"""頁面層級的元素操作、腳本、滑鼠鍵盤、frame / Page-level interaction."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver._playwright_mixins._common import PlaywrightBackendError, recorded


class _InteractionMixin:
    """以 selector 直接操作元素、執行腳本、滑鼠與鍵盤、frame 查詢。

    Selector-based element shortcuts, script evaluation, mouse and keyboard,
    and frame lookup.
    """

    @recorded()
    def click(self, selector: str, **options: Any) -> None:
        web_runner_logger.info(f"playwright click: {selector}")
        self.page.click(selector, **options)

    @recorded()
    def dblclick(self, selector: str, **options: Any) -> None:
        self.page.dblclick(selector, **options)

    @recorded()
    def hover(self, selector: str, **options: Any) -> None:
        self.page.hover(selector, **options)

    @recorded()
    def fill(self, selector: str, value: str, **options: Any) -> None:
        web_runner_logger.info(f"playwright fill: {selector}")
        self.page.fill(selector, value, **options)

    @recorded()
    def type_text(self, selector: str, value: str, delay: float = 0, **options: Any) -> None:
        self.page.type(selector, value, delay=delay, **options)

    @recorded()
    def press(self, selector: str, key: str, **options: Any) -> None:
        self.page.press(selector, key, **options)

    @recorded()
    def check(self, selector: str, **options: Any) -> None:
        self.page.check(selector, **options)

    @recorded()
    def uncheck(self, selector: str, **options: Any) -> None:
        self.page.uncheck(selector, **options)

    @recorded()
    def select_option(self, selector: str, value: Any, **options: Any) -> list[str]:
        return self.page.select_option(selector, value, **options)

    @recorded()
    def drag_and_drop(self, source_selector: str, target_selector: str, **options: Any) -> None:
        self.page.drag_and_drop(source_selector, target_selector, **options)

    @recorded()
    def drag_and_drop_offset(self, selector: str, target_x: float, target_y: float) -> None:
        """Drag the element matching ``selector`` by ``(target_x, target_y)`` pixels from its centre."""
        box = self.page.locator(selector).bounding_box()
        if box is None:
            raise PlaywrightBackendError(f"element {selector!r} is not visible")
        start_x, start_y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        self.page.mouse.move(start_x, start_y)
        self.page.mouse.down()
        self.page.mouse.move(start_x + target_x, start_y + target_y, steps=5)
        self.page.mouse.up()

    @recorded()
    def scroll(self, scroll_x: float, scroll_y: float) -> None:
        """Scroll by ``(scroll_x, scroll_y)`` pixels with the mouse wheel."""
        self.page.mouse.wheel(scroll_x, scroll_y)

    @recorded()
    def scroll_to_top(self) -> None:
        self.page.evaluate("window.scrollTo(0, 0)")

    @recorded()
    def scroll_to_bottom(self) -> None:
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    # ----- script ------------------------------------------------------

    @recorded()
    def evaluate(self, expression: str, arg: Any = None):
        return self.page.evaluate(expression, arg) if arg is not None else self.page.evaluate(expression)

    def evaluate_handle(self, expression: str, arg: Any = None):
        if arg is not None:
            return self.page.evaluate_handle(expression, arg)
        return self.page.evaluate_handle(expression)

    @recorded()
    def mouse_click(self, x: float, y: float, button: str = "left", click_count: int = 1) -> None:
        self.page.mouse.click(x, y, button=button, click_count=click_count)

    @recorded()
    def mouse_move(self, x: float, y: float, steps: int = 1) -> None:
        self.page.mouse.move(x, y, steps=steps)

    @recorded()
    def mouse_down(self, button: str = "left", click_count: int = 1) -> None:
        self.page.mouse.down(button=button, click_count=click_count)

    @recorded()
    def mouse_up(self, button: str = "left", click_count: int = 1) -> None:
        self.page.mouse.up(button=button, click_count=click_count)

    @recorded()
    def keyboard_press(self, key: str) -> None:
        self.page.keyboard.press(key)

    @recorded()
    def keyboard_type(self, text: str, delay: float = 0) -> None:
        self.page.keyboard.type(text, delay=delay)

    @recorded()
    def keyboard_down(self, key: str) -> None:
        self.page.keyboard.down(key)

    @recorded()
    def keyboard_up(self, key: str) -> None:
        self.page.keyboard.up(key)

    # ----- frames ------------------------------------------------------

    def frames(self) -> list[Any]:
        return list(self.page.frames)

    def main_frame(self) -> Any:
        return self.page.main_frame
