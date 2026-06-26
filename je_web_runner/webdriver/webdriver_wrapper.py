"""
WebDriverWrapper：以 mixin 組合的 Selenium 包裝器入口。
WebDriverWrapper: Selenium wrapper assembled from theme-specific mixins.

各主題方法分散在 ``_wrapper_mixins/`` 下，本檔保留：
This file keeps only:

* 瀏覽器 / Options / webdriver_manager 對應表 (測試會 ``patch.dict`` 這幾個名稱)
  Browser / Options / webdriver_manager dicts (test code ``patch.dict``s these)
* ``WebDriverWrapper`` 類別本體 (__init__ + 生命週期 + 元素 + 等待 + quit)
  The ``WebDriverWrapper`` class itself (lifecycle + element finding + waits + quit)
* ``webdriver_wrapper_instance`` 全域單例 / module-level singleton
"""
from __future__ import annotations

import typing
from functools import partial
from pathlib import Path

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chromium.options import ArgOptions as ChromiumOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.ie.options import Options as IEOptions, Options
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager, ChromeType
from webdriver_manager.core.driver_cache import DriverCacheManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager, IEDriverManager

from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.utils.assert_value.result_check import check_webdriver_details
from je_web_runner.utils.exception.exception_tags import selenium_wrapper_web_driver_not_found_error
from je_web_runner.utils.exception.exceptions import WebRunnerException, WebRunnerWebDriverNotFoundException, \
    WebRunnerWebDriverIsNoneException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_object.test_object_class import TestObject
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.test_record.test_record_class import record_action_to_list
from je_web_runner.webdriver._wrapper_mixins import (
    _ActionsMixin,
    _CookieMixin,
    _MediaMixin,
    _NavigationMixin,
    _ScriptingMixin,
)
from je_web_runner.webdriver.webdriver_with_options import set_webdriver_options_capability_wrapper

# 瀏覽器名稱對應到 WebDriver 類別
# Mapping browser names to WebDriver classes
_webdriver_dict = {
    "chrome": webdriver.Chrome,
    "chromium": webdriver.Chrome,
    "firefox": webdriver.Firefox,
    "edge": webdriver.Edge,
    "ie": webdriver.Ie,
    "safari": webdriver.Safari,
}

# 瀏覽器名稱對應到 webdriver_manager 安裝器
# Mapping browser names to webdriver_manager installers
# Every value must be *callable with no args* — the caller does
# ``_webdriver_manager_dict.get(name)().install()``. ``chromium`` needs a
# constructor kwarg, so wrap it in ``partial`` rather than pre-instantiating
# it (a bare instance is not callable → ``instance()`` raised TypeError, and
# pre-building it ran the manager's setup at import time).
_webdriver_manager_dict = {
    "chrome": ChromeDriverManager,
    "chromium": partial(ChromeDriverManager, chrome_type=ChromeType.CHROMIUM),
    "firefox": GeckoDriverManager,
    "edge": EdgeChromiumDriverManager,
    "ie": IEDriverManager,
}

# 瀏覽器名稱對應到 Options 類別
# Mapping browser names to Options classes
_options_dict = {
    "chrome": ChromeOptions,
    "chromium": ChromiumOptions,
    "firefox": FirefoxOptions,
    "edge": EdgeOptions,
    "ie": IEOptions,
    "safari": SafariOptions,
}


def _apply_experimental_options(driver_options, webdriver_name, experimental_options) -> None:
    """逐項套用 Chromium 系實驗性參數，若 Options 不支援則拋出。"""
    if not hasattr(driver_options, "add_experimental_option"):
        raise WebRunnerException(
            f"{webdriver_name!r} options do not support experimental_options "
            f"(Chromium-family browsers only)"
        )
    for exp_key, exp_value in experimental_options.items():
        driver_options.add_experimental_option(exp_key, exp_value)


def _apply_extension_paths(driver_options, webdriver_name, extension_paths) -> None:
    """逐項載入瀏覽器擴充功能 (.crx)，若 Options 不支援則拋出。"""
    if not hasattr(driver_options, "add_extension"):
        raise WebRunnerException(
            f"{webdriver_name!r} options do not support add_extension"
        )
    for ext_path in extension_paths:
        driver_options.add_extension(ext_path)


def _build_driver_options(
        webdriver_name: str,
        options: list[str] | None,
        experimental_options: dict | None,
        extension_paths: list[str] | None,
        enable_bidi: bool,
):
    """
    依旗標組裝 Options 物件；若所有參數都空或瀏覽器沒有對應 Options 類別，回傳 None
    讓呼叫端走 ``webdriver_value(**kwargs)`` 路徑。
    Build the Options object based on the flag set; return ``None`` when nothing
    needs to be configured (or the browser has no Options class), so the caller
    can take the ``webdriver_value(**kwargs)`` path.
    """
    if not (options or experimental_options or extension_paths or enable_bidi):
        return None
    options_cls = _options_dict.get(webdriver_name)
    if options_cls is None:
        return None
    driver_options = options_cls()
    if options:
        for option in options:
            driver_options.add_argument(argument=option)
    if experimental_options:
        _apply_experimental_options(driver_options, webdriver_name, experimental_options)
    if extension_paths:
        _apply_extension_paths(driver_options, webdriver_name, extension_paths)
    if enable_bidi:
        driver_options.set_capability("webSocketUrl", True)
    return driver_options


class WebDriverWrapper(
    _ScriptingMixin,
    _NavigationMixin,
    _CookieMixin,
    _ActionsMixin,
    _MediaMixin,
):
    """
    WebDriver 包裝器
    WebDriver wrapper to manage browser drivers and options.

    Mixin 組成 / Mixin composition::

        _ScriptingMixin   — execute / execute_script / execute_cdp_cmd /
                            BiDi listener / Fetch 攔截 (放最前以提供 execute_cdp_cmd
                            給其他 mixin 使用)
        _NavigationMixin  — to_url / forward / back / scroll / switch / window
        _CookieMixin      — cookies + clear_origin_storage
        _ActionsMixin     — ActionChains 全集
        _MediaMixin       — 截圖 / PDF 列印 / get_log

    本類別本身保留：driver 生命週期、元素查找、等待、check / quit。
    This class itself keeps: driver lifecycle, element finding, waits, check / quit.
    """

    def __init__(self):
        self.current_webdriver: WebDriver | None = None
        self._webdriver_name: str | None = None
        self._action_chain: ActionChains | None = None

    def set_driver(
            self,
            webdriver_name: str,
            webdriver_manager_option_dict: dict | None = None,
            options: list[str] | None = None,
            experimental_options: dict | None = None,
            extension_paths: list[str] | None = None,
            enable_bidi: bool = False,
            **kwargs
    ) -> webdriver.Chrome | webdriver.Firefox | webdriver.Edge | webdriver.Ie | webdriver.Safari:
        """
        啟動一個新的 WebDriver
        Start a new WebDriver instance

        :param webdriver_name: 瀏覽器名稱 (chrome, firefox, edge, ie, safari)
                               Browser name
        :param webdriver_manager_option_dict: webdriver_manager 的額外參數 (目前未使用)
                                              Extra options for webdriver_manager (currently unused)
        :param options: 瀏覽器啟動參數 (例如 ["--headless", "--disable-gpu"])
                        Browser startup arguments
        :param experimental_options: Chromium 系瀏覽器專屬實驗性參數 (Chrome / Chromium / Edge)，
                                     會逐項經由 ``add_experimental_option`` 傳入。例如
                                     ``{"excludeSwitches": ["enable-automation"],
                                     "useAutomationExtension": False,
                                     "prefs": {"download.default_directory": "./downloads"}}``。
                                     非 Chromium 系瀏覽器若傳入會拋出例外。
                                     Browser-specific experimental options for Chromium-family
                                     browsers (Chrome / Chromium / Edge), each forwarded via
                                     ``add_experimental_option``. Raises on non-Chromium browsers.
        :param extension_paths: 要載入的瀏覽器擴充功能檔案路徑 (.crx)。會逐一呼叫
                                ``Options.add_extension(path)``。僅 Chromium 系與 Firefox 支援；
                                其他瀏覽器若傳入會拋出例外。
                                List of browser extension file paths (.crx) to load via
                                ``Options.add_extension(path)``. Chromium-family and Firefox only.
        :param enable_bidi: 啟用 W3C WebDriver BiDi (``webSocketUrl=True`` capability)，
                            供 ``add_console_listener`` / ``add_js_error_listener`` 等 BiDi
                            事件 API 使用。需 Selenium 4.16+。
                            Enable W3C WebDriver BiDi (``webSocketUrl=True`` capability) so
                            ``add_console_listener`` / ``add_js_error_listener`` work.
                            Requires Selenium 4.16+.
        :param kwargs: 額外傳給 WebDriver 的參數
                       Extra kwargs passed to WebDriver
        :return: 啟動後的 WebDriver 實例
                 The started WebDriver instance
        """
        web_runner_logger.info(
            f"WebDriverWrapper set_driver, webdriver_name: {webdriver_name}, "
            f"webdriver_manager_option_dict: {webdriver_manager_option_dict}"
        )
        param = locals()
        install_path: str = str(Path.cwd())
        cache_manager = DriverCacheManager(install_path)

        try:
            webdriver_name = str(webdriver_name).lower()
            webdriver_value = _webdriver_dict.get(webdriver_name)

            if webdriver_value is None:
                raise WebRunnerWebDriverNotFoundException(selenium_wrapper_web_driver_not_found_error)

            # 使用 webdriver_manager 安裝對應的 driver
            webdriver_install_manager = _webdriver_manager_dict.get(webdriver_name)
            webdriver_install_manager().install()

            driver_options = _build_driver_options(
                webdriver_name, options, experimental_options, extension_paths, enable_bidi,
            )
            if driver_options is not None:
                self.current_webdriver = webdriver_value(options=driver_options, **kwargs)
            else:
                self.current_webdriver = webdriver_value(**kwargs)

            self._webdriver_name = webdriver_name
            self._action_chain = ActionChains(self.current_webdriver)

            record_action_to_list("webdriver wrapper set_driver", param, None)
            return self.current_webdriver

        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper set_driver, webdriver_name: {webdriver_name}, "
                f"webdriver_manager_option_dict: {webdriver_manager_option_dict}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper set_driver", param, error)
            raise WebRunnerException from error

    def set_webdriver_options_capability(self, key_and_vale_dict: dict) -> Options | None:
        """
        設定 WebDriver 的 capabilities
        Set WebDriver capabilities

        :param key_and_vale_dict: 要設定的 capabilities (dict)
                                  capabilities to set
        :return: 當前 WebDriver / current webdriver
        """
        web_runner_logger.info(
            f"WebDriverWrapper set_webdriver_options_capability, "
            f"key_and_vale_dict: {key_and_vale_dict}"
        )
        param = locals()
        try:
            if self._webdriver_name is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            record_action_to_list("webdriver wrapper set_webdriver_options_capability", param, None)
            return set_webdriver_options_capability_wrapper(self._webdriver_name, key_and_vale_dict)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper set_webdriver_options_capability, "
                f"key_and_vale_dict: {key_and_vale_dict}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper set_webdriver_options_capability", param, error)
            raise WebRunnerException from error

    def attach_to_existing_browser(
            self,
            debugger_address: str,
            webdriver_name: str = "chrome",
            options: list[str] | None = None,
            experimental_options: dict | None = None,
            **kwargs,
    ):
        """
        附加到一個已啟動且開啟 remote debugging 埠的 Chrome / Edge 實例。
        Attach to an already-running Chrome / Edge that was started with
        ``--remote-debugging-port``.

        典型用法（使用者先手動啟動 Chrome）::

            chrome.exe --remote-debugging-port=9222 --user-data-dir="C:/temp/profile"

        然後在腳本中::

            webdriver_wrapper_instance.attach_to_existing_browser("127.0.0.1:9222")

        :param debugger_address: ``host:port``，例如 ``"127.0.0.1:9222"``
        :param webdriver_name: 預設 ``"chrome"``，亦可為 ``"edge"`` / ``"chromium"``
        :param options: 額外 CLI 啟動參數 (一般 attach 場景不需要)
        :param experimental_options: 其他要合併的實驗性參數
        :return: 已連接的 WebDriver 實例 / attached WebDriver instance
        """
        web_runner_logger.info(
            f"WebDriverWrapper attach_to_existing_browser, debugger_address: {debugger_address}, "
            f"webdriver_name: {webdriver_name}"
        )
        merged_exp = dict(experimental_options or {})
        merged_exp["debuggerAddress"] = debugger_address
        return self.set_driver(
            webdriver_name,
            options=options,
            experimental_options=merged_exp,
            **kwargs,
        )

    # web element
    def find_element(self, test_object: TestObject) -> WebElement | None:
        """
        使用 TestObject 尋找單一元素
        Find a single element using TestObject

        :param test_object: 測試物件 (包含定位方式與名稱)
                            TestObject containing locator type and value
        :return: 找到的 WebElement / found WebElement
        """
        web_runner_logger.info(f"WebDriverWrapper find_element, test_object: {test_object}")
        param = locals()
        try:
            if self.current_webdriver is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                test_object.test_object_type, test_object.test_object_name
            )
            record_action_to_list("webdriver wrapper find_element", param, None)
            return web_element_wrapper.current_web_element
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper find_element, test_object: {test_object}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper find_element", param, error)

    def find_elements(self, test_object: TestObject) -> list[WebElement] | None:
        """
        使用 TestObject 尋找多個元素
        Find multiple elements using TestObject

        :param test_object: 測試物件 (包含定位方式與名稱)
                            TestObject containing locator type and value
        :return: WebElement 清單 / list of WebElements
        """
        web_runner_logger.info(f"WebDriverWrapper find_elements, test_object: {test_object}")
        param = locals()
        try:
            if self.current_webdriver is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            web_element_wrapper.current_web_element_list = self.current_webdriver.find_elements(
                test_object.test_object_type, test_object.test_object_name
            )
            record_action_to_list("webdriver wrapper find_elements", param, None)
            return web_element_wrapper.current_web_element_list
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper find_elements, test_object: {test_object}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper find_elements", param, error)

    def find_element_with_test_object_record(self, element_name: str) -> WebElement | None:
        """
        使用已儲存的 TestObjectRecord 尋找單一元素
        Find a single element using stored TestObjectRecord

        :param element_name: 測試物件名稱 / test object name
        :return: 找到的 WebElement / found WebElement
        """
        web_runner_logger.info(
            f"WebDriverWrapper find_element_with_test_object_record, element_name: {element_name}"
        )
        param = locals()
        try:
            if self.current_webdriver is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            record = test_object_record.test_object_record_dict.get(element_name)
            if record is None:
                raise WebRunnerException(f"TestObject '{element_name}' not found in record")
            web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                record.test_object_type, record.test_object_name
            )
            record_action_to_list("webdriver wrapper find_element_with_test_object_record", param, None)
            return web_element_wrapper.current_web_element
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper find_element_with_test_object_record, element_name: {element_name}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper find_element_with_test_object_record", param, error)

    def find_elements_with_test_object_record(self, element_name: str) -> list[WebElement] | None:
        """
        使用已儲存的 TestObjectRecord 尋找多個元素
        Find multiple elements using stored TestObjectRecord

        :param element_name: 測試物件名稱 / test object name
        :return: WebElement 清單 / list of WebElements
        """
        web_runner_logger.info(
            f"WebDriverWrapper find_elements_with_test_object_record, element_name: {element_name}"
        )
        param = locals()
        try:
            if self.current_webdriver is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            record = test_object_record.test_object_record_dict.get(element_name)
            if record is None:
                raise WebRunnerException(f"TestObject '{element_name}' not found in record")
            web_element_wrapper.current_web_element_list = self.current_webdriver.find_elements(
                record.test_object_type, record.test_object_name
            )
            record_action_to_list("webdriver wrapper find_elements_with_test_object_record", param, None)
            return web_element_wrapper.current_web_element_list
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper find_elements_with_test_object_record, element_name: {element_name}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper find_elements_with_test_object_record", param, error)

    # wait
    def implicitly_wait(self, time_to_wait: int) -> None:
        """
        設定 Selenium 的隱式等待時間
        Set Selenium implicit wait time

        :param time_to_wait: 等待秒數 / number of seconds to wait
        """
        web_runner_logger.info(f"WebDriverWrapper implicitly_wait, time_to_wait: {time_to_wait}")
        param = locals()
        try:
            self.current_webdriver.implicitly_wait(time_to_wait)
            record_action_to_list("webdriver wrapper implicitly_wait", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper implicitly_wait, time_to_wait: {time_to_wait}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper implicitly_wait", param, error)

    def explict_wait(self, wait_time: int, method: typing.Callable | None = None, until_type: bool = True):
        """
        Selenium 顯式等待
        Selenium explicit wait

        :param wait_time: 最長等待時間 (秒) / max wait time in seconds
        :param method: 條件方法 (回傳 True/False) / condition method returning True/False
        :param until_type: True = until, False = until_not
        :return: 條件成立時回傳結果 / result when condition is met
        """
        web_runner_logger.info(
            f"WebDriverWrapper explict_wait, wait_time: {wait_time}, method: {method}, until_type: {until_type}"
        )
        param = locals()
        try:
            record_action_to_list("webdriver wrapper explict_wait", param, None)
            if until_type and method:
                return WebDriverWait(self.current_webdriver, wait_time).until(method)
            if until_type is False and method:
                return WebDriverWait(self.current_webdriver, wait_time).until_not(method)
            return WebDriverWait(self.current_webdriver, wait_time)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper explict_wait failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper explict_wait", param, error)

    # timeout
    def set_script_timeout(self, time_to_wait: int) -> None:
        """設定 script 最大執行時間 / Set max script execution time"""
        web_runner_logger.info(f"WebDriverWrapper set_script_timeout, time_to_wait: {time_to_wait}")
        param = locals()
        try:
            self.current_webdriver.set_script_timeout(time_to_wait)
            record_action_to_list("webdriver wrapper set_script_timeout", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper set_script_timeout failed: {error!r}")
            record_action_to_list("webdriver wrapper set_script_timeout", param, error)

    def set_page_load_timeout(self, time_to_wait: int) -> None:
        """設定頁面載入最大等待時間 / Set max page load wait time"""
        web_runner_logger.info(f"WebDriverWrapper set_page_load_timeout, time_to_wait: {time_to_wait}")
        param = locals()
        try:
            self.current_webdriver.set_page_load_timeout(time_to_wait)
            record_action_to_list("webdriver wrapper set_page_load_timeout", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper set_page_load_timeout failed: {error!r}")
            record_action_to_list("webdriver wrapper set_page_load_timeout", param, error)

    # webdriver wrapper add function
    def check_current_webdriver(self, check_dict: dict) -> None:
        """
        驗證當前 WebDriver 狀態，若不符合會拋出例外
        Check current WebDriver state, raise exception if validation fails

        :param check_dict: 驗證條件 (dict)
        """
        web_runner_logger.info(f"WebDriverWrapper check_current_webdriver, check_dict: {check_dict}")
        param = locals()
        try:
            check_webdriver_details(self.current_webdriver, check_dict)
            record_action_to_list("webdriver wrapper check_current_webdriver", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper check_current_webdriver failed: {error!r}")
            record_action_to_list("webdriver wrapper check_current_webdriver", param, error)

    # close event
    def quit(self) -> None:
        """
        關閉並退出 WebDriver
        Quit this WebDriver
        """
        web_runner_logger.info("WebDriverWrapper quit")
        try:
            test_object_record.clean_record()  # 清空測試物件紀錄
            self._action_chain = None
            record_action_to_list("webdriver wrapper quit", None, None)
            self.current_webdriver.quit()
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper quit failed: {error!r}")
            record_action_to_list("webdriver wrapper quit", None, error)
            raise WebRunnerException from error


# 全域單例，方便直接使用
webdriver_wrapper_instance = WebDriverWrapper()
