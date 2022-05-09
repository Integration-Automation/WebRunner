from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.edge.service import Service
from selenium.webdriver.ie.service import Service
from selenium.webdriver.safari.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.opera import OperaDriverManager
from webdriver_manager.microsoft import IEDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.utils import ChromeType

from je_web_runner.utils.exception.exceptions import WebDriverException, WebDriverIsNoneException
from je_web_runner.utils.exception.exceptions import WebDriverNotFoundException

from je_web_runner.utils.exception.exception_tag import selenium_wrapper_web_driver_not_found_error
from je_web_runner.utils.exception.exception_tag import selenium_wrapper_opera_path_error

from je_web_runner.selenium_webdrive_wrapper.webdriver_quit_wrapper import quit_wrapper

from je_web_runner.test_object.test_object import TestObject

from je_web_runner.selenium_webdrive_wrapper.webdriver_find_wrapper import find_element_with_test_object_record
from je_web_runner.selenium_webdrive_wrapper.webdriver_find_wrapper import find_elements_with_test_object_record

from je_web_runner.selenium_webdrive_wrapper.webdriver_with_options import set_webdriver_options_capability_wrapper


webdriver_manager_dict = {
    "chrome": ChromeDriverManager,
    "chromium": ChromeDriverManager(chrome_type=ChromeType.CHROMIUM),
    "firefox": GeckoDriverManager,
    "opera": OperaDriverManager,
    "edge": EdgeChromiumDriverManager,
    "ie": IEDriverManager,
}

webdriver_service_dict = {
    "chrome": webdriver.chrome.service.Service,
    "chromium": webdriver.chrome.service.Service,
    "firefox": webdriver.firefox.service.Service,
    "edge": webdriver.edge.service.Service,
    "ie": webdriver.ie.service.Service,
    "safari": webdriver.safari.service.Service,
}

webdriver_dict = {
    "chrome": webdriver.Chrome,
    "chromium": webdriver.Chrome,
    "firefox": webdriver.Firefox,
    "opera": webdriver.Opera,
    "edge": webdriver.Edge,
    "ie": webdriver.Ie,
    "safari": webdriver.Safari,
}


class WebdriverWrapper(object):

    def __init__(self, **kwargs):
        self.webdriver_name = None
        self.webdriver = None
        self.current_webdriver_list = []

    def set_driver(self, webdriver_name: str, opera_path: str = None, **kwargs):
        webdriver_name = str(webdriver_name).lower()
        webdriver_value = webdriver_dict.get(webdriver_name)
        if webdriver_value is None:
            raise WebDriverNotFoundException(selenium_wrapper_web_driver_not_found_error)
        webdriver_install_manager = webdriver_manager_dict.get(webdriver_name)
        if webdriver_name in ["opera"]:
            if opera_path is None:
                raise WebDriverException(selenium_wrapper_opera_path_error)
            opera_options = webdriver.ChromeOptions()
            opera_options.add_argument('allow-elevated-browser')
            opera_options.binary_location = opera_path
            self.webdriver = webdriver_value(
                executable_path=webdriver_manager_dict.get(webdriver_name)().install(), options=opera_options, **kwargs
            )
        else:
            webdriver_service = webdriver_service_dict.get(webdriver_name)(
                webdriver_install_manager().install(),
            )
            self.webdriver = webdriver_value(service=webdriver_service, **kwargs)
            self.webdriver_name = webdriver_name
        self.current_webdriver_list.append(self.webdriver)
        return self.webdriver

    def open_browser(self, url: str):
        self.webdriver.get(url)

    def set_webdriver_options_capability(self, key_and_vale_dict: dict):
        if self.webdriver_name is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        set_webdriver_options_capability_wrapper(self.webdriver_name, key_and_vale_dict)

    def find_element(self, test_object: TestObject):
        if self.webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        return find_element_with_test_object_record(self.webdriver, test_object)

    def find_elements(self, test_object: TestObject):
        if self.webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        return find_elements_with_test_object_record(self.webdriver, test_object)

    def quit(self):
        if self.webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        quit_wrapper(self.webdriver, self.current_webdriver_list)


web_runner = WebdriverWrapper()
