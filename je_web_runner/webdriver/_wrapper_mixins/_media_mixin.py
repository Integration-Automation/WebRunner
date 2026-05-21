"""截圖、PDF 列印、driver log / Screenshots, PDF printing, driver log."""
from __future__ import annotations

import base64

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class _MediaMixin:
    """截圖 / 列印 / log 取得 / Screenshots, printing, and driver log retrieval."""

    def save_screenshot(self, file_path: str) -> bool:
        """
        將當前頁面截圖儲存至指定路徑 (PNG)
        Save current page screenshot to the given file path (PNG)

        :param file_path: 目標檔案路徑 / target file path
        :return: 截圖是否成功儲存 / True if saved
        """
        web_runner_logger.info(f"WebDriverWrapper save_screenshot, file_path: {file_path}")
        param = locals()
        try:
            result = self.current_webdriver.save_screenshot(file_path)
            record_action_to_list("webdriver wrapper save_screenshot", param, None)
            return bool(result)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper save_screenshot failed: {repr(error)}")
            record_action_to_list("webdriver wrapper save_screenshot", param, error)
            return False

    def get_screenshot_as_png(self) -> bytes | None:
        """
        取得當前頁面截圖 (PNG 格式)
        Get current page screenshot as PNG

        :return: PNG 截圖的 bytes
        """
        web_runner_logger.info("WebDriverWrapper get_screenshot_as_png")
        try:
            record_action_to_list("webdriver wrapper get_screenshot_as_png", None, None)
            return self.current_webdriver.get_screenshot_as_png()
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_screenshot_as_png failed: {repr(error)}")
            record_action_to_list("webdriver wrapper get_screenshot_as_png", None, error)

    def save_full_page_screenshot(self, file_path: str) -> bool:
        """
        將整個頁面 (含可視範圍外) 截圖儲存為 PNG，透過 CDP
        ``Page.captureScreenshot`` 並啟用 ``captureBeyondViewport``。
        Save a full-page screenshot (beyond the visible viewport) as PNG,
        via CDP ``Page.captureScreenshot`` with ``captureBeyondViewport``.

        僅 Chromium 系瀏覽器支援。
        Chromium-family browsers only.

        :param file_path: 目標檔案路徑 / target file path
        :return: 是否成功儲存 / True if saved
        """
        web_runner_logger.info(f"WebDriverWrapper save_full_page_screenshot, file_path: {file_path}")
        param = locals()
        try:
            result = self.execute_cdp_cmd(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": True, "fromSurface": True},
            )
            data_b64 = (result or {}).get("data")
            if not data_b64:
                record_action_to_list("webdriver wrapper save_full_page_screenshot", param, None)
                return False
            with open(file_path, "wb") as fh:
                fh.write(base64.b64decode(data_b64))
            record_action_to_list("webdriver wrapper save_full_page_screenshot", param, None)
            return True
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper save_full_page_screenshot failed: {repr(error)}")
            record_action_to_list("webdriver wrapper save_full_page_screenshot", param, error)
            return False

    def print_page(self, file_path: str, print_options=None) -> bool:
        """
        將當前頁面列印為 PDF 並存檔 (Selenium 4 內建 ``print_page``)。
        Print the current page to PDF and save (uses Selenium 4 ``print_page``).

        :param file_path: 目標 PDF 檔案路徑 / target PDF path
        :param print_options: 選填，Selenium 的 ``PrintOptions`` 實例
                              Optional Selenium ``PrintOptions`` instance
        :return: 是否成功儲存 / True if saved
        """
        web_runner_logger.info(f"WebDriverWrapper print_page, file_path: {file_path}")
        param = locals()
        try:
            data_b64 = (
                self.current_webdriver.print_page(print_options)
                if print_options is not None
                else self.current_webdriver.print_page()
            )
            if not data_b64:
                record_action_to_list("webdriver wrapper print_page", param, None)
                return False
            with open(file_path, "wb") as fh:
                fh.write(base64.b64decode(data_b64))
            record_action_to_list("webdriver wrapper print_page", param, None)
            return True
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper print_page failed: {repr(error)}")
            record_action_to_list("webdriver wrapper print_page", param, error)
            return False

    def get_screenshot_as_base64(self) -> str | None:
        """
        取得當前頁面截圖 (Base64 字串)
        Get current page screenshot as Base64 string

        :return: Base64 字串
        """
        web_runner_logger.info("WebDriverWrapper get_screenshot_as_base64")
        try:
            record_action_to_list("webdriver wrapper get_screenshot_as_base64", None, None)
            return self.current_webdriver.get_screenshot_as_base64()
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_screenshot_as_base64 failed: {repr(error)}")
            record_action_to_list("webdriver wrapper get_screenshot_as_base64", None, error)

    def get_log(self, log_type: str):
        """
        取得 WebDriver 日誌（``log_type`` 為必填）
        Get WebDriver logs (``log_type`` is required).

        :param log_type: 必填，需為下列之一：
                         Required; one of:

                         - ``"browser"`` — JS console output (Chrome/Edge)
                         - ``"driver"``  — driver-side messages
                         - ``"client"``  — client-side bindings logs
                         - ``"server"``  — Selenium server logs
                         - ``"performance"`` — perf log (only when enabled in capabilities)

                         不同瀏覽器支援的子集不同；Firefox 自 GeckoDriver 後幾乎不再
                         提供，多數情況請改用 Playwright 的 console-event capture。
                         Browser support varies; modern Firefox no longer exposes most
                         of these, prefer Playwright's console-event capture instead.
        :return: log 資料 (list of dict) / log entries
        """
        web_runner_logger.info(f"WebDriverWrapper get_log, log_type: {log_type}")
        try:
            record_action_to_list("webdriver wrapper get_log", None, None)
            return self.current_webdriver.get_log(log_type)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_log failed: {repr(error)}")
            record_action_to_list("webdriver wrapper get_log", None, error)
