
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.utils.exception.exception_tags import selenium_wrapper_web_driver_not_found_error
from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverIsNoneException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.test_record.test_record_class import record_action_to_list
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class WebdriverManager:
    def __init__(self, **kwargs):
        # 當前 WebDriver 實例清單
        # List of current WebDriver instances
        self._current_webdriver_list = []

        # WebDriver 包裝器
        # WebDriver wrapper
        self.webdriver_wrapper = webdriver_wrapper_instance

        # WebElement 包裝器
        # WebElement wrapper
        self.webdriver_element = web_element_wrapper

        # 當前使用的 WebDriver
        # Current active WebDriver
        self.current_webdriver: WebDriver | None = None

    def new_driver(self, webdriver_name: str, options: list[str] | None = None, **kwargs) -> None:
        """
        建立新的 WebDriver 實例
        Create a new WebDriver instance

        :param webdriver_name: 要使用的 WebDriver 名稱 [chrome, chromium, firefox, edge, ie]
                               The WebDriver to use [chrome, chromium, firefox, edge, ie]
        :param options: 瀏覽器啟動選項 / browser startup options
        :param kwargs: 額外參數 (例如下載管理設定) / additional parameters (e.g., download manager)
        """
        web_runner_logger.info(f"WebdriverManager new_driver, webdriver_name: {webdriver_name}, params: {kwargs}")
        param = locals()
        try:
            # 建立 WebDriver 並加入清單
            # Create WebDriver and add to list
            self.current_webdriver = webdriver_wrapper_instance.set_driver(webdriver_name, options=options, **kwargs)
            self._current_webdriver_list.append(self.current_webdriver)
            record_action_to_list("web runner manager new_driver", param, None)
        except Exception as error:
            # 錯誤處理與關閉所有 WebDriver
            # Handle error and quit all WebDrivers
            web_runner_logger.error(
                f"WebdriverManager new_driver, webdriver_name: {webdriver_name}, params: {kwargs}, failed: {error!r}"
            )
            record_action_to_list("web runner manager new_driver", param, error)
            self.quit()

    def change_webdriver(self, index_of_webdriver: int) -> None:
        """
        切換當前 WebDriver
        Change the current WebDriver

        :param index_of_webdriver: WebDriver 清單中的索引 / index in WebDriver list
        """
        web_runner_logger.info(f"WebdriverManager change_webdriver, index_of_webdriver: {index_of_webdriver}")
        param = locals()
        try:
            self.current_webdriver = self._current_webdriver_list[index_of_webdriver]
            # Rebind via set_active_driver so the wrapper's ActionChains follow
            # the switched driver instead of staying on the previous one.
            self.webdriver_wrapper.set_active_driver(self.current_webdriver)
            record_action_to_list("web runner manager change_webdriver", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebdriverManager change_webdriver, index_of_webdriver: {index_of_webdriver}, failed: {error!r}")
            record_action_to_list("web runner manager change_webdriver", param, error)

    def _detach_wrapper_if_active(self, driver: WebDriver) -> None:
        """
        若共用的 wrapper 單例正指向這個已關閉的 driver，就把它解除綁定。
        Clear the shared ``webdriver_wrapper`` singleton when it is still
        pointing at ``driver``. The manager owns raw Selenium handles, so
        closing one here would otherwise leave the wrapper (and its
        ActionChains) bound to a dead session for the next caller.
        """
        if self.webdriver_wrapper.current_webdriver is driver:
            self.webdriver_wrapper.set_active_driver(None)

    def close_current_webdriver(self) -> None:
        """
        關閉當前 WebDriver
        Close the current WebDriver
        """
        web_runner_logger.info("WebdriverManager close_current_webdriver")
        try:
            if self.current_webdriver is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            # Close first, then drop the reference: if close() raises, the
            # driver stays tracked so a later quit() can still reclaim it.
            closed = self.current_webdriver
            closed.close()
            if closed in self._current_webdriver_list:
                self._current_webdriver_list.remove(closed)
            # Never leave ``current_webdriver`` pointing at a closed session —
            # the next action would fail against a dead driver.
            self.current_webdriver = None
            self._detach_wrapper_if_active(closed)
            record_action_to_list("web runner manager close_current_webdriver", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebdriverManager close_current_webdriver, failed: {error!r}")
            record_action_to_list("web runner manager close_current_webdriver", None, error)

    def close_choose_webdriver(self, webdriver_index: int) -> None:
        """
        關閉指定索引的 WebDriver
        Close a WebDriver by index

        :param webdriver_index: WebDriver 清單中的索引 / index in WebDriver list
        """
        web_runner_logger.info("WebdriverManager close_choose_webdriver")
        param = locals()
        try:
            chosen = self._current_webdriver_list[webdriver_index]
            chosen.close()
            self._current_webdriver_list.pop(webdriver_index)
            if self.current_webdriver is chosen:
                self.current_webdriver = None
            self._detach_wrapper_if_active(chosen)
            record_action_to_list("web runner manager close_choose_webdriver", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebdriverManager close_choose_webdriver, failed: {error!r}")
            record_action_to_list("web runner manager close_choose_webdriver", param, error)

    def quit(self) -> None:
        """
        關閉並退出所有 WebDriver
        Close and quit all WebDriver instances
        """
        web_runner_logger.info("WebdriverManager quit")
        try:
            if self._current_webdriver_list is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)

            # 清理測試紀錄
            # Clean test records
            test_object_record.clean_record()

            # 關閉所有 WebDriver；單一 driver 失敗不可中斷其餘的清理，
            # 否則剩下的瀏覽器程序會變成 orphan。
            # Quit every WebDriver. A failure on one must not abort the loop,
            # or the remaining browsers leak as orphan processes.
            quit_errors: list[Exception] = []
            for webdriver in self._current_webdriver_list:
                try:
                    webdriver.quit()
                except Exception as error:  # pylint: disable=broad-except
                    web_runner_logger.error(f"WebdriverManager quit driver failed: {error!r}")
                    quit_errors.append(error)

            self._current_webdriver_list = []
            self.current_webdriver = None
            # Every driver is gone, so the shared wrapper singleton must not
            # keep serving a dead one to the next caller.
            self.webdriver_wrapper.set_active_driver(None)
            if quit_errors:
                raise WebDriverException(
                    f"WebdriverManager quit failed for {len(quit_errors)} driver(s): "
                    f"{[repr(e) for e in quit_errors]}"
                )
            record_action_to_list("web runner manager quit", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebdriverManager quit, failed: {error!r}")
            record_action_to_list("web runner manager quit", None, error)
            raise WebDriverException(f"WebdriverManager quit failed: {error!r}") from error


def get_webdriver_manager(webdriver_name: str, **kwargs) -> WebdriverManager:
    """
    取得 WebDriver 管理器
    Get WebDriver manager

    :param webdriver_name: 要使用的 WebDriver 名稱 [chrome, chromium, firefox, edge, ie]
                           The WebDriver to use [chrome, chromium, firefox, edge, ie]
    :param kwargs: 額外參數 (例如下載管理設定) / additional parameters (e.g., download manager)
    :return: WebdriverManager 實例 / WebdriverManager instance
    """
    web_runner_logger.info(f"get_webdriver_manager, webdriver_name: {webdriver_name}, params: {kwargs}")
    web_runner.new_driver(webdriver_name, **kwargs)
    return web_runner


# 全域 WebDriver 管理器實例
# Global WebDriver manager instance
web_runner = WebdriverManager()