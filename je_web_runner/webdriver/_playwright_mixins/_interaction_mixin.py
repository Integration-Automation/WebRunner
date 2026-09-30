"""頁面層級的元素操作、腳本、滑鼠鍵盤、frame / Page-level interaction."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class _InteractionMixin:
    """以 selector 直接操作元素、執行腳本、滑鼠與鍵盤、frame 查詢。

    Selector-based element shortcuts, script evaluation, mouse and keyboard,
    and frame lookup.
    """

    def click(self, selector: str, **options: Any) -> None:
        web_runner_logger.info(f"playwright click: {selector}")
        self.page.click(selector, **options)

    def dblclick(self, selector: str, **options: Any) -> None:
        self.page.dblclick(selector, **options)

    def hover(self, selector: str, **options: Any) -> None:
        self.page.hover(selector, **options)

    def fill(self, selector: str, value: str, **options: Any) -> None:
        web_runner_logger.info(f"playwright fill: {selector}")
        self.page.fill(selector, value, **options)

    def type_text(self, selector: str, value: str, delay: float = 0) -> None:
        self.page.type(selector, value, delay=delay)

    def press(self, selector: str, key: str) -> None:
        self.page.press(selector, key)

    def check(self, selector: str) -> None:
        self.page.check(selector)

    def uncheck(self, selector: str) -> None:
        self.page.uncheck(selector)

    def select_option(self, selector: str, value: Any) -> list[str]:
        return self.page.select_option(selector, value)

    def drag_and_drop(self, source_selector: str, target_selector: str, **options: Any) -> None:
        self.page.drag_and_drop(source_selector, target_selector, **options)

    # ----- script ------------------------------------------------------

    def evaluate(self, expression: str, arg: Any = None):
        return self.page.evaluate(expression, arg) if arg is not None else self.page.evaluate(expression)

    def evaluate_handle(self, expression: str, arg: Any = None):
        if arg is not None:
            return self.page.evaluate_handle(expression, arg)
        return self.page.evaluate_handle(expression)

    def mouse_click(self, x: float, y: float, button: str = "left", click_count: int = 1) -> None:
        self.page.mouse.click(x, y, button=button, click_count=click_count)

    def mouse_move(self, x: float, y: float, steps: int = 1) -> None:
        self.page.mouse.move(x, y, steps=steps)

    def mouse_down(self, button: str = "left", click_count: int = 1) -> None:
        self.page.mouse.down(button=button, click_count=click_count)

    def mouse_up(self, button: str = "left", click_count: int = 1) -> None:
        self.page.mouse.up(button=button, click_count=click_count)

    def keyboard_press(self, key: str) -> None:
        self.page.keyboard.press(key)

    def keyboard_type(self, text: str, delay: float = 0) -> None:
        self.page.keyboard.type(text, delay=delay)

    def keyboard_down(self, key: str) -> None:
        self.page.keyboard.down(key)

    def keyboard_up(self, key: str) -> None:
        self.page.keyboard.up(key)

    # ----- frames ------------------------------------------------------

    def frames(self) -> list[Any]:
        return list(self.page.frames)

    def main_frame(self) -> Any:
        return self.page.main_frame
