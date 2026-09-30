"""
原生視窗操作 / Steps outside the page that a browser driver cannot reach, through AutoControl.

The operating system's file picker, pixels on the screen and a real (trusted) mouse click
are outside what WebDriver and Playwright can do. These commands type and look through
AutoControl instead, on this machine's real screen. They therefore refuse a Selenium
driver whose window is not on that screen: a headless browser, or a remote one (a grid or
a device cloud). A Playwright browser is not checked, because Playwright does not report
whether it was launched headless; launch it with ``headless=False``.
"""
from __future__ import annotations

import os
import time
from typing import Any

from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.utils.autocontrol_bridge.bridge import AutoControlBridgeError, ac_run, ac_run_actions
from je_web_runner.utils.autocontrol_bridge.screen_mapping import METRICS_SCRIPT, element_center_on_screen
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver._wrapper_mixins._parity_mixin import resolve_by
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


def _local_driver_classes() -> tuple[type, ...]:
    from selenium.webdriver import Firefox, Ie, Safari
    from selenium.webdriver.chromium.webdriver import ChromiumDriver
    return ChromiumDriver, Firefox, Safari, Ie


def invisible_reason(driver: Any) -> str | None:
    """
    瀏覽器視窗不在這台機器螢幕上的原因；看得到時回傳 None
    Why ``driver``'s window is not on this machine's screen (remote or headless), or None.
    """
    if not isinstance(driver, _local_driver_classes()):
        return f"the current driver ({type(driver).__name__}) is remote: its window is on another machine"
    if (getattr(driver, "capabilities", None) or {}).get("moz:headless") is True:
        return "the current Firefox is headless"
    user_agent = str(driver.execute_script("return navigator.userAgent") or "")
    if "Headless" in user_agent:
        return "the current browser is headless"
    return None


def require_visible_browser() -> None:
    """Raise :class:`AutoControlBridgeError` when the current Selenium driver has no window on this screen."""
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        return
    reason = invisible_reason(driver)
    if reason is not None:
        raise AutoControlBridgeError(f"{reason}; native commands act on this machine's screen")


def _enter_key() -> str:
    """AutoControl's name for Enter: ``return`` on Windows, ``enter`` elsewhere."""
    table = ac_run(["AC_get_keyboard_keys_table"])
    for name in ("enter", "return"):
        if name in table:
            return name
    raise AutoControlBridgeError("AutoControl's key table has neither 'enter' nor 'return'")


def fill_native_file_dialog(file_path: str, submit: bool = True, wait_seconds: float = 1.0) -> str:
    """
    在已開啟的系統檔案對話框輸入路徑並按 Enter
    Type ``file_path`` (made absolute) into the operating system's file dialog, which must
    already be open with its file-name field focused (a click on a file input or a
    download's Save As opens it), then press Enter unless ``submit`` is False. Waits
    ``wait_seconds`` first for the dialog to appear. Returns the path typed.
    """
    if not isinstance(file_path, str) or not file_path.strip():
        raise AutoControlBridgeError("file_path must be a non-empty path")
    if any(char in file_path for char in "\r\n\t"):
        raise AutoControlBridgeError("file_path must not contain line breaks or tabs; they would press keys")
    require_visible_browser()
    absolute = os.path.abspath(file_path)
    time.sleep(max(0.0, float(wait_seconds)))  # a native dialog has no DOM to wait on
    actions: list[list[Any]] = [["AC_write", {"write_string": absolute}]]
    if submit:
        actions.append(["AC_type_keyboard", {"keycode": _enter_key()}])
    web_runner_logger.info(f"fill_native_file_dialog: {absolute}")
    ac_run_actions(actions)
    return absolute


def assert_image_on_screen(image_path: str, detect_threshold: float | None = None) -> list[int]:
    """
    斷言螢幕上看得到指定圖片，回傳其中心座標
    Assert that the template image ``image_path`` is on the screen and return its centre
    ``[x, y]`` in AutoControl's screen coordinates. ``detect_threshold`` is AutoControl's
    match threshold (its default when None). Raises :class:`AutoControlBridgeError` when
    the image is not found.
    """
    if not isinstance(image_path, str) or not os.path.isfile(image_path):
        raise AutoControlBridgeError(f"image_path is not a file: {image_path!r}")
    require_visible_browser()
    params: dict[str, Any] = {"image": image_path}
    if detect_threshold is not None:
        params["detect_threshold"] = float(detect_threshold)
    center = ac_run(["AC_locate_image_center", params])
    return [int(center[0]), int(center[1])]


def click_element_native(selector: str | None = None, by: str = "css selector",
                         mouse_button: str = "mouse_left", scale: float | None = None) -> list[int]:
    """
    用真正的滑鼠點擊元素（不是 WebDriver 的合成點擊）
    Click an element with the real mouse through AutoControl: the element found by
    ``selector`` (``by`` as in ``WR_find_element_by``), else the current element. It is
    scrolled to the middle of the viewport, its centre is mapped to screen coordinates
    (:func:`~je_web_runner.utils.autocontrol_bridge.screen_mapping.element_center_on_screen`;
    ``scale`` is the monitor's display scale, taken from ``devicePixelRatio`` when None,
    which is right at 100 % page zoom), and ``mouse_button`` is clicked there. The window
    must be on screen and not covered. Returns the clicked ``[x, y]``.
    """
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise AutoControlBridgeError("no Selenium driver is running")
    require_visible_browser()
    element = driver.find_element(resolve_by(by), selector) if selector else web_element_wrapper.current_web_element
    if element is None:
        raise AutoControlBridgeError("pass a selector or find an element first")
    x, y = element_center_on_screen(driver.execute_script(METRICS_SCRIPT, element), scale)
    web_runner_logger.info(f"click_element_native: {mouse_button} at ({x}, {y})")
    ac_run(["AC_click_mouse", {"mouse_keycode": mouse_button, "x": x, "y": y}])
    return [x, y]
