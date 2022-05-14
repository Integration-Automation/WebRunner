from selenium.webdriver.remote.webdriver import WebDriver
from selenium import webdriver

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.opera import OperaDriverManager
from webdriver_manager.microsoft import IEDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.utils import ChromeType

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.edge.service import Service
from selenium.webdriver.ie.service import Service
from selenium.webdriver.safari.service import Service

from je_web_runner.utils.test_object.test_object_class import TestObject

from je_web_runner.selenium_wrapper.webdriver_with_options import set_webdriver_options_capability_wrapper
from je_web_runner.utils.assert_value.result_check import check_webdriver
from je_web_runner.utils.exception.exceptions import WebDriverException, WebDriverIsNoneException
from je_web_runner.utils.exception.exceptions import WebDriverNotFoundException

from je_web_runner.utils.exception.exception_tag import selenium_wrapper_web_driver_not_found_error
from je_web_runner.utils.exception.exception_tag import selenium_wrapper_opera_path_error

from je_web_runner.selenium_wrapper.web_element_wrapper import web_element_wrapper
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record

_webdriver_dict = {
    "chrome": webdriver.Chrome,
    "chromium": webdriver.Chrome,
    "firefox": webdriver.Firefox,
    "opera": webdriver.Opera,
    "edge": webdriver.Edge,
    "ie": webdriver.Ie,
    "safari": webdriver.Safari,
}

_webdriver_manager_dict = {
    "chrome": ChromeDriverManager,
    "chromium": ChromeDriverManager(chrome_type=ChromeType.CHROMIUM),
    "firefox": GeckoDriverManager,
    "opera": OperaDriverManager,
    "edge": EdgeChromiumDriverManager,
    "ie": IEDriverManager,
}

_webdriver_service_dict = {
    "chrome": webdriver.chrome.service.Service,
    "chromium": webdriver.chrome.service.Service,
    "firefox": webdriver.firefox.service.Service,
    "edge": webdriver.edge.service.Service,
    "ie": webdriver.ie.service.Service,
    "safari": webdriver.safari.service.Service,
}


class WebDriverWrapper(object):

    def __init__(self):
        self.current_webdriver: [WebDriver, None] = None
        self.webdriver_name: [str, None] = None

    def set_driver(self, webdriver_name: str, opera_path: str = None, **kwargs):
        webdriver_name = str(webdriver_name).lower()
        webdriver_value = _webdriver_dict.get(webdriver_name)
        if webdriver_value is None:
            raise WebDriverNotFoundException(selenium_wrapper_web_driver_not_found_error)
        webdriver_install_manager = _webdriver_manager_dict.get(webdriver_name)
        if webdriver_name in ["opera"]:
            if opera_path is None:
                raise WebDriverException(selenium_wrapper_opera_path_error)
            opera_options = webdriver.ChromeOptions()
            opera_options.add_argument('allow-elevated-browser')
            opera_options.binary_location = opera_path
            self.current_webdriver = webdriver_value(
                executable_path=_webdriver_manager_dict.get(webdriver_name)().install(), options=opera_options, **kwargs
            )
        else:
            webdriver_service = _webdriver_service_dict.get(webdriver_name)(
                webdriver_install_manager().install(),
            )
            self.current_webdriver = webdriver_value(service=webdriver_service, **kwargs)
            self.webdriver_name = webdriver_name
        return self.current_webdriver

    def to_url(self, url: str):
        self.current_webdriver.get(url)

    def set_webdriver_options_capability(self, key_and_vale_dict: dict):
        if self.webdriver_name is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        set_webdriver_options_capability_wrapper(self.webdriver_name, key_and_vale_dict)

    def find_element(self, test_object: TestObject):
        if self.current_webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        web_element_wrapper.current_web_element = self.current_webdriver.find_element(
            test_object.test_object_type, test_object.test_object_name)
        return web_element_wrapper.current_web_element

    def find_elements(self, test_object: TestObject):
        if self.current_webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        web_element_wrapper.current_web_element_list = self.current_webdriver.find_elements(
            test_object.test_object_type, test_object.test_object_name)
        return web_element_wrapper.current_web_element_list

    def find_element_with_test_object_record(self, element_name: str):
        if self.current_webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        web_element_wrapper.current_web_element = self.current_webdriver.find_element(
            test_object_record.test_object_record_dict.get(element_name).test_object_type,
            test_object_record.test_object_record_dict.get(element_name).test_object_name
        )
        return web_element_wrapper.current_web_element

    def find_elements_with_test_object_record(self, element_name: str):
        if self.current_webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        web_element_wrapper.current_web_element_list = self.current_webdriver.find_elements(
            test_object_record.test_object_record_dict.get(element_name).test_object_type,
            test_object_record.test_object_record_dict.get(element_name).test_object_name
        )
        return web_element_wrapper.current_web_element

    def wait_implicitly(self, time_to_wait: int):
        self.current_webdriver.implicitly_wait(time_to_wait)

    def check_current_webdriver(self, check_dict: dict):
        check_webdriver(self.current_webdriver, check_dict)

    def quit(self):
        test_object_record.clean_record()
        self.current_webdriver.quit()


webdriver_wrapper = WebDriverWrapper()
