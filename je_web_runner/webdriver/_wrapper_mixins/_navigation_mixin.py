"""導航、捲動、視窗 / Page navigation, scrolling, window management."""
from __future__ import annotations

from selenium.common import NoAlertPresentException

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class _NavigationMixin:
    """URL 導航、捲動、tab / window 切換、視窗大小位置。

    URL navigation, scrolling, tab/window switching, and window geometry.
    """

    # webdriver url redirect
    def to_url(self, url: str) -> None:
        """
        導航到指定 URL
        Navigate to a given URL
        """
        web_runner_logger.info(f"WebDriverWrapper to_url, url: {url}")
        param = locals()
        try:
            self.current_webdriver.get(url)
            record_action_to_list("webdriver wrapper to_url", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper to_url failed: {repr(error)}")
            record_action_to_list("webdriver wrapper to_url", param, error)

    def forward(self) -> None:
        """前進到下一頁 / Navigate forward"""
        web_runner_logger.info("WebDriverWrapper forward")
        try:
            self.current_webdriver.forward()
            record_action_to_list("webdriver wrapper forward", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper forward failed: {repr(error)}")
            record_action_to_list("webdriver wrapper forward", None, error)

    def back(self) -> None:
        """返回上一頁 / Navigate back"""
        web_runner_logger.info("WebDriverWrapper back")
        try:
            self.current_webdriver.back()
            record_action_to_list("webdriver wrapper back", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper back failed: {repr(error)}")
            record_action_to_list("webdriver wrapper back", None, error)

    def refresh(self) -> None:
        """重新整理頁面 / Refresh current page"""
        web_runner_logger.info("WebDriverWrapper refresh")
        try:
            self.current_webdriver.refresh()
            record_action_to_list("webdriver wrapper refresh", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper refresh failed: {repr(error)}")
            record_action_to_list("webdriver wrapper refresh", None, error)

    def reload(self, ignore_cache: bool = False) -> None:
        """
        重新整理頁面，可選擇是否旁路快取 (透過 CDP ``Page.reload``)。
        Reload the current page, optionally bypassing the cache (via CDP ``Page.reload``).

        :param ignore_cache: True 表示忽略 HTTP cache，等同瀏覽器的 Ctrl+Shift+R
                             True bypasses HTTP cache (equivalent to Ctrl+Shift+R)
        """
        if ignore_cache:
            self.execute_cdp_cmd("Page.reload", {"ignoreCache": True})
        else:
            self.refresh()

    def scroll_to_element(self, element) -> None:
        """
        將指定元素捲動到可視範圍 (JS ``scrollIntoView({block: 'center'})``)。
        Scroll a given element into view via JS ``scrollIntoView({block: 'center'})``.
        """
        web_runner_logger.info("WebDriverWrapper scroll_to_element")
        try:
            self.current_webdriver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
                element,
            )
            record_action_to_list("webdriver wrapper scroll_to_element", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper scroll_to_element failed: {repr(error)}")
            record_action_to_list("webdriver wrapper scroll_to_element", None, error)

    def scroll_to_top(self) -> None:
        """捲動到頁面最上方 / Scroll to the top of the page"""
        web_runner_logger.info("WebDriverWrapper scroll_to_top")
        try:
            self.current_webdriver.execute_script("window.scrollTo(0, 0);")
            record_action_to_list("webdriver wrapper scroll_to_top", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper scroll_to_top failed: {repr(error)}")
            record_action_to_list("webdriver wrapper scroll_to_top", None, error)

    def scroll_to_bottom(self) -> None:
        """捲動到頁面最下方 / Scroll to the bottom of the page"""
        web_runner_logger.info("WebDriverWrapper scroll_to_bottom")
        try:
            self.current_webdriver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            record_action_to_list("webdriver wrapper scroll_to_bottom", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper scroll_to_bottom failed: {repr(error)}")
            record_action_to_list("webdriver wrapper scroll_to_bottom", None, error)

    def bring_to_front(self) -> None:
        """
        將瀏覽器視窗叫到最上層 (透過 CDP ``Page.bringToFront``)。
        Bring the browser window to the foreground via CDP ``Page.bringToFront``.
        """
        self.execute_cdp_cmd("Page.bringToFront")

    def switch_to_window_by_url(self, pattern: str) -> bool:
        """
        遍歷所有 window handle，切換到第一個 URL 含 ``pattern`` 子字串的視窗。
        Iterate window handles and switch to the first whose URL contains ``pattern``.

        :param pattern: 子字串比對 (大小寫敏感) / case-sensitive substring match
        :return: 是否找到並切換 / True if matched and switched
        """
        return self._switch_to_window_by_attr("current_url", pattern)

    def switch_to_window_by_title(self, pattern: str) -> bool:
        """
        遍歷所有 window handle，切換到第一個 title 含 ``pattern`` 子字串的視窗。
        Iterate window handles and switch to the first whose title contains ``pattern``.

        :param pattern: 子字串比對 (大小寫敏感) / case-sensitive substring match
        :return: 是否找到並切換 / True if matched and switched
        """
        return self._switch_to_window_by_attr("title", pattern)

    def _switch_to_window_by_attr(self, attr_name: str, pattern: str) -> bool:
        """共用實作：依 driver 屬性 (current_url / title) 子字串比對切換視窗。"""
        web_runner_logger.info(
            f"WebDriverWrapper _switch_to_window_by_attr, attr: {attr_name}, pattern: {pattern}"
        )
        original = None
        try:
            original = self.current_webdriver.current_window_handle
            for handle in self.current_webdriver.window_handles:
                self.current_webdriver.switch_to.window(handle)
                if pattern in (getattr(self.current_webdriver, attr_name) or ""):
                    return True
            if original is not None:
                self.current_webdriver.switch_to.window(original)
            return False
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper _switch_to_window_by_attr failed: {repr(error)}"
            )
            if original is not None:
                try:
                    self.current_webdriver.switch_to.window(original)
                except Exception:  # noqa: BLE001 — best-effort restore
                    pass
            return False

    # page / window metadata
    def get_current_url(self) -> str | None:
        """
        取得當前頁面的 URL
        Get the current page URL
        """
        web_runner_logger.info("WebDriverWrapper get_current_url")
        try:
            record_action_to_list("webdriver wrapper get_current_url", None, None)
            return self.current_webdriver.current_url
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_current_url failed: {repr(error)}")
            record_action_to_list("webdriver wrapper get_current_url", None, error)
            return None

    def get_title(self) -> str | None:
        """
        取得當前頁面的 <title>
        Get the current page title
        """
        web_runner_logger.info("WebDriverWrapper get_title")
        try:
            record_action_to_list("webdriver wrapper get_title", None, None)
            return self.current_webdriver.title
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_title failed: {repr(error)}")
            record_action_to_list("webdriver wrapper get_title", None, error)
            return None

    def get_page_source(self) -> str | None:
        """
        取得當前頁面 HTML 原始碼
        Get the current page HTML source
        """
        web_runner_logger.info("WebDriverWrapper get_page_source")
        try:
            record_action_to_list("webdriver wrapper get_page_source", None, None)
            return self.current_webdriver.page_source
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_page_source failed: {repr(error)}")
            record_action_to_list("webdriver wrapper get_page_source", None, error)
            return None

    def get_window_handles(self) -> list[str] | None:
        """
        取得所有開啟中的視窗 / tab handle
        Get all open window / tab handles
        """
        web_runner_logger.info("WebDriverWrapper get_window_handles")
        try:
            record_action_to_list("webdriver wrapper get_window_handles", None, None)
            return self.current_webdriver.window_handles
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_window_handles failed: {repr(error)}")
            record_action_to_list("webdriver wrapper get_window_handles", None, error)
            return None

    def get_current_window_handle(self) -> str | None:
        """
        取得當前 driver 操作的視窗 handle
        Get the handle of the window currently driven
        """
        web_runner_logger.info("WebDriverWrapper get_current_window_handle")
        try:
            record_action_to_list("webdriver wrapper get_current_window_handle", None, None)
            return self.current_webdriver.current_window_handle
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_current_window_handle failed: {repr(error)}")
            record_action_to_list("webdriver wrapper get_current_window_handle", None, error)
            return None

    def new_window(self, type_hint: str = "tab") -> None:
        """
        開啟新的 tab 或 window，並自動切換到該視窗
        Open a new tab or window and switch focus to it.

        :param type_hint: ``"tab"`` (預設) 或 ``"window"`` / ``"tab"`` (default) or ``"window"``
        """
        web_runner_logger.info(f"WebDriverWrapper new_window, type_hint: {type_hint}")
        param = locals()
        try:
            self.current_webdriver.switch_to.new_window(type_hint)
            record_action_to_list("webdriver wrapper new_window", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper new_window failed: {repr(error)}")
            record_action_to_list("webdriver wrapper new_window", param, error)

    def close_window(self) -> None:
        """
        關閉當前 tab / window (不會結束整個 driver；要結束請用 ``quit``)
        Close the current tab / window (does not quit the whole driver; use ``quit`` for that)
        """
        web_runner_logger.info("WebDriverWrapper close_window")
        try:
            self.current_webdriver.close()
            record_action_to_list("webdriver wrapper close_window", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper close_window failed: {repr(error)}")
            record_action_to_list("webdriver wrapper close_window", None, error)

    # webdriver new page
    def switch(self, switch_type: str, switch_target_name: str = None):
        """
        切換 WebDriver 的上下文 (frame, window, alert...)
        Switch WebDriver context (frame, window, alert...)

        :param switch_type: [active_element, default_content, frame, parent_frame, window, alert]
        :param switch_target_name: 目標名稱 (frame 名稱或 window handle)
        :return: 切換後的目標物件 / switched target
        """
        web_runner_logger.info(
            f"WebDriverWrapper switch, switch_type: {switch_type}, switch_target_name: {switch_target_name}"
        )
        param = locals()
        try:
            switch_type = switch_type.lower()
            switch_type_dict = {
                "active_element": self.current_webdriver.switch_to.active_element,
                "default_content": self.current_webdriver.switch_to.default_content,
                "frame": self.current_webdriver.switch_to.frame,
                "parent_frame": self.current_webdriver.switch_to.parent_frame,
                "window": self.current_webdriver.switch_to.window,
            }
            try:
                switch_type_dict.update({"alert": self.current_webdriver.switch_to.alert})
            except NoAlertPresentException as error:
                switch_type_dict.update({"alert": None})
                web_runner_logger.error(f"WebDriverWrapper switch alert failed: {repr(error)}")

            record_action_to_list("webdriver wrapper switch", param, None)
            if switch_type in ["active_element", "alert"]:
                return switch_type_dict.get(switch_type)
            elif switch_type in ["default_content", "parent_frame"]:
                return switch_type_dict.get(switch_type)()
            else:
                return switch_type_dict.get(switch_type)(switch_target_name)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper switch failed: {repr(error)}")
            record_action_to_list("webdriver wrapper switch", param, error)

    # window geometry
    def maximize_window(self) -> None:
        """
        最大化當前視窗
        Maximize the current browser window
        """
        web_runner_logger.info("WebDriverWrapper maximize_window")
        try:
            self.current_webdriver.maximize_window()
            record_action_to_list("webdriver wrapper maximize_window", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper maximize_window failed: {repr(error)}")
            record_action_to_list("webdriver wrapper maximize_window", None, error)

    def fullscreen_window(self) -> None:
        """
        全螢幕顯示當前視窗
        Fullscreen the current browser window
        """
        web_runner_logger.info("WebDriverWrapper fullscreen_window")
        try:
            self.current_webdriver.fullscreen_window()
            record_action_to_list("webdriver wrapper fullscreen_window", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper fullscreen_window failed: {repr(error)}")
            record_action_to_list("webdriver wrapper fullscreen_window", None, error)

    def minimize_window(self) -> None:
        """
        最小化當前視窗
        Minimize the current browser window
        """
        web_runner_logger.info("WebDriverWrapper minimize_window")
        try:
            self.current_webdriver.minimize_window()
            record_action_to_list("webdriver wrapper minimize_window", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper minimize_window failed: {repr(error)}")
            record_action_to_list("webdriver wrapper minimize_window", None, error)

    def set_window_size(self, width: int, height: int, window_handle: str = 'current') -> None:
        """
        設定視窗大小
        Set the window size

        :param width: 視窗寬度 (像素) / window width in pixels
        :param height: 視窗高度 (像素) / window height in pixels
        :param window_handle: 預設為 "current" (w3c 標準)，若非 "current" 可能會拋出例外
                              normally "current" (w3c), otherwise may raise exception
        :return: 視窗大小資訊 (dict) / window size info (dict)
        """
        web_runner_logger.info(
            f"WebDriverWrapper set_window_size, width: {width}, height: {height}, window_handle: {window_handle}"
        )
        param = locals()
        try:
            record_action_to_list("webdriver wrapper set_window_size", param, None)
            self.current_webdriver.set_window_size(width, height, window_handle)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper set_window_size failed: {repr(error)}"
            )
            record_action_to_list("webdriver wrapper set_window_size", param, error)

    def set_window_position(self, x: int, y: int, window_handle: str = 'current') -> dict | None:
        """
        設定視窗位置
        Set the window position

        :param x: 視窗左上角的 X 座標 / X coordinate of the window
        :param y: 視窗左上角的 Y 座標 / Y coordinate of the window
        :param window_handle: 預設為 "current" (w3c 標準)，若非 "current" 可能會拋出例外
                              normally "current" (w3c), otherwise may raise exception
        :return: 視窗位置與大小資訊 (dict) / window rect info (dict)
        """
        web_runner_logger.info(
            f"WebDriverWrapper set_window_position, x: {x}, y: {y}, window_handle: {window_handle}"
        )
        param = locals()
        try:
            record_action_to_list("webdriver wrapper set_window_position", param, None)
            return self.current_webdriver.set_window_position(x, y, window_handle)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper set_window_position failed: {repr(error)}"
            )
            record_action_to_list("webdriver wrapper set_window_position", param, error)

    def get_window_position(self, window_handle='current') -> dict | None:
        """
        取得視窗位置
        Get window position

        :param window_handle: 預設為 "current" (w3c 標準)，若非 "current" 可能會拋出例外
        :return: 視窗位置 dict，例如 {"x": 100, "y": 200}
        """
        web_runner_logger.info(f"WebDriverWrapper get_window_position, window_handle: {window_handle}")
        param = locals()
        try:
            record_action_to_list("webdriver wrapper get_window_position", param, None)
            return self.current_webdriver.get_window_position(window_handle)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_window_position failed: {repr(error)}")
            record_action_to_list("webdriver wrapper get_window_position", param, error)

    def get_window_rect(self) -> dict | None:
        """
        取得視窗矩形資訊 (位置與大小)
        Get window rect (position and size)

        :return: dict, e.g. {"x": 100, "y": 200, "width": 1280, "height": 720}
        """
        web_runner_logger.info("WebDriverWrapper get_window_rect")
        try:
            record_action_to_list("webdriver wrapper get_window_rect", None, None)
            return self.current_webdriver.get_window_rect()
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_window_rect failed: {repr(error)}")
            record_action_to_list("webdriver wrapper get_window_rect", None, error)

    def set_window_rect(self, x: int = None, y: int = None, width: int = None, height: int = None) -> dict | None:
        """
        設定視窗矩形 (位置與大小)，僅支援 W3C 相容瀏覽器
        Set window rect (position and size), only supported for W3C compatible browsers

        :param x: X 座標
        :param y: Y 座標
        :param width: 視窗寬度
        :param height: 視窗高度
        :return: dict, e.g. {"x": 100, "y": 200, "width": 1280, "height": 720}
        """
        web_runner_logger.info(
            f"WebDriverWrapper set_window_rect, x: {x}, y: {y}, width: {width}, height: {height}")
        param = locals()
        try:
            record_action_to_list("webdriver wrapper set_window_rect", param, None)
            return self.current_webdriver.set_window_rect(x, y, width, height)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper set_window_rect failed: {repr(error)}")
            record_action_to_list("webdriver wrapper set_window_rect", param, error)
