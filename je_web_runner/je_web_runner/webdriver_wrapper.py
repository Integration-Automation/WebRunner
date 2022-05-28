from typing import List, Union

from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.edge.service import Service
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.ie.service import Service
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.safari.service import Service
from selenium.webdriver.support.wait import WebDriverWait

from je_web_runner.je_web_runner.web_element_wrapper import web_element_wrapper
from je_web_runner.je_web_runner.webdriver_with_options import set_webdriver_options_capability_wrapper
from je_web_runner.utils.assert_value.result_check import check_webdriver
from je_web_runner.utils.exception.exception_tag import selenium_wrapper_opera_path_error
from je_web_runner.utils.exception.exception_tag import selenium_wrapper_web_driver_not_found_error
from je_web_runner.utils.exception.exceptions import WebDriverException, WebDriverIsNoneException
from je_web_runner.utils.exception.exceptions import WebDriverNotFoundException
from je_web_runner.utils.test_object.test_object_class import TestObject
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.webdriver_manager.chrome import ChromeDriverManager
from je_web_runner.webdriver_manager.firefox import GeckoDriverManager
from je_web_runner.webdriver_manager.microsoft import EdgeChromiumDriverManager
from je_web_runner.webdriver_manager.microsoft import IEDriverManager
from je_web_runner.webdriver_manager.opera import OperaDriverManager
from je_web_runner.webdriver_manager.utils import ChromeType
from je_web_runner.utils.test_record.test_record import record_action_to_list

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
        self._webdriver_name: [str, None] = None
        self._action_chain: [ActionChains, None] = None

    # start a new webdriver

    def set_driver(self, webdriver_name: str, opera_path: str = None, **kwargs) -> \
            Union[
            webdriver.Chrome,
            webdriver.Chrome,
            webdriver.Firefox,
            webdriver.Opera,
            webdriver.Edge,
            webdriver.Ie,
            webdriver.Safari,
            ]:
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
            self._webdriver_name = webdriver_name
            self._action_chain = ActionChains(self.current_webdriver)
        return self.current_webdriver

    def set_webdriver_options_capability(self, key_and_vale_dict: dict) -> \
            Union[
            webdriver.Chrome,
            webdriver.Chrome,
            webdriver.Firefox,
            webdriver.Opera,
            webdriver.Edge,
            webdriver.Ie,
            webdriver.Safari,
            ]:
        if self._webdriver_name is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        return set_webdriver_options_capability_wrapper(self._webdriver_name, key_and_vale_dict)

    # web element
    def find_element(self, test_object: TestObject) -> WebElement:
        if self.current_webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        web_element_wrapper.current_web_element = self.current_webdriver.find_element(
            test_object.test_object_type, test_object.test_object_name)
        return web_element_wrapper.current_web_element

    def find_elements(self, test_object: TestObject) -> List[WebElement]:
        if self.current_webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        web_element_wrapper.current_web_element_list = self.current_webdriver.find_elements(
            test_object.test_object_type, test_object.test_object_name)
        return web_element_wrapper.current_web_element_list

    def find_element_with_test_object_record(self, element_name: str) -> WebElement:
        if self.current_webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        web_element_wrapper.current_web_element = self.current_webdriver.find_element(
            test_object_record.test_object_record_dict.get(element_name).test_object_type,
            test_object_record.test_object_record_dict.get(element_name).test_object_name
        )
        return web_element_wrapper.current_web_element

    def find_elements_with_test_object_record(self, element_name: str) -> List[WebElement]:
        if self.current_webdriver is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        web_element_wrapper.current_web_element_list = self.current_webdriver.find_elements(
            test_object_record.test_object_record_dict.get(element_name).test_object_type,
            test_object_record.test_object_record_dict.get(element_name).test_object_name
        )
        return web_element_wrapper.current_web_element

    # wait

    def implicitly_wait(self, time_to_wait: int) -> None:
        self.current_webdriver.implicitly_wait(time_to_wait)

    def explict_wait(self, wait_time: int, statement: bool, until_type: bool = True):
        if until_type:
            return WebDriverWait(self.current_webdriver, wait_time).until(statement)
        else:
            return WebDriverWait(self.current_webdriver, wait_time).until_not(statement)

    # webdriver url redirect

    def to_url(self, url: str) -> None:
        self.current_webdriver.get(url)

    def forward(self) -> None:
        self.current_webdriver.forward()

    def back(self) -> None:
        self.current_webdriver.back()

    def refresh(self) -> None:
        self.current_webdriver.refresh()

    # webdriver new page
    def switch(self, switch_type: str, switchy_target_name: str = None):
        switch_type = switch_type.lower()
        switch_type_dict = {
            "active_element": self.current_webdriver.switch_to.active_element,
            "default_content": self.current_webdriver.switch_to.default_content,
            "frame": self.current_webdriver.switch_to.frame,
            "parent_frame": self.current_webdriver.switch_to.parent_frame,
            "window": self.current_webdriver.switch_to.window,
        }
        try:
            switch_type_dict.update(
                {"alert": self.current_webdriver.switch_to.alert}
            )
        except NoAlertPresentException as error:
            switch_type_dict.update(
                {"alert": None}
            )
        if switch_type in ["active_element", "alert"]:
            return switch_type_dict.get(switch_type)
        elif switch_type in ["default_content", "parent_frame"]:
            return switch_type_dict.get(switch_type)()
        else:
            return switch_type_dict.get(switch_type)(switchy_target_name)

    # timeout
    def set_script_timeout(self, time_to_wait) -> None:
        self.current_webdriver.set_script_timeout(time_to_wait)

    def set_page_load_timeout(self, time_to_wait) -> None:
        self.current_webdriver.set_page_load_timeout(time_to_wait)

    # cookie
    def get_cookies(self) -> List[dict]:
        return self.current_webdriver.get_cookies()

    def get_cookie(self, name) -> dict:
        return self.current_webdriver.get_cookie(name)

    def add_cookie(self, cookie_dict: dict):
        self.current_webdriver.add_cookie(cookie_dict)

    def delete_cookie(self, name) -> None:
        self.current_webdriver.delete_cookie(name)

    def delete_all_cookies(self) -> None:
        self.current_webdriver.delete_all_cookies()

    # exec selenium command
    def execute(self, driver_command: str, params: dict = None) -> dict:
        return self.current_webdriver.execute(driver_command, params)

    def execute_script(self, script, *args):
        self.current_webdriver.execute_script(script, *args)

    def execute_async_script(self, script: str, *args):
        self.current_webdriver.execute_async_script(script, *args)

    # ActionChains
    def move_to_element(self, targe_element: WebElement):
        self._action_chain.move_to_element(targe_element)

    def move_to_element_with_test_object(self, element_name: str):
        element = self.current_webdriver.find_element(
            test_object_record.test_object_record_dict.get(element_name).test_object_type,
            test_object_record.test_object_record_dict.get(element_name).test_object_name
        )
        self._action_chain.move_to_element(element)

    def move_to_element_with_offset(self, target_element: WebElement, x: int, y: int):
        self._action_chain.move_to_element_with_offset(target_element, x, y)

    def move_to_element_with_offset_and_test_object(self, element_name: str, x: int, y: int):
        element = self.current_webdriver.find_element(
            test_object_record.test_object_record_dict.get(element_name).test_object_type,
            test_object_record.test_object_record_dict.get(element_name).test_object_name
        )
        self._action_chain.move_to_element_with_offset(element, x, y)

    def drag_and_drop(self, web_element: WebElement, targe_element: WebElement):
        self._action_chain.drag_and_drop(web_element, targe_element)

    def drag_and_drop_with_test_object(self, element_name: str, target_element_name: str):
        element = self.current_webdriver.find_element(
            test_object_record.test_object_record_dict.get(element_name).test_object_type,
            test_object_record.test_object_record_dict.get(element_name).test_object_name
        )
        another_element = self.current_webdriver.find_element(
            test_object_record.test_object_record_dict.get(target_element_name).test_object_type,
            test_object_record.test_object_record_dict.get(target_element_name).test_object_name
        )
        self._action_chain.drag_and_drop(element, another_element)

    def drag_and_drop_offset(self, web_element: WebElement, target_x: int, target_y: int):
        self._action_chain.drag_and_drop_by_offset(web_element, target_x, target_y)

    def drag_and_drop_offset_with_test_object(self, element_name: str, target_x: int, target_y: int):
        element = self.current_webdriver.find_element(
            test_object_record.test_object_record_dict.get(element_name).test_object_type,
            test_object_record.test_object_record_dict.get(element_name).test_object_name
        )
        self._action_chain.drag_and_drop_by_offset(element, target_x, target_y)

    def perform(self):
        self._action_chain.perform()

    def reset_actions(self):
        self._action_chain.reset_actions()

    def left_click(self, on_element: WebElement = None):
        self._action_chain.click(on_element)

    def left_click_with_test_object(self, element_name: str = None):
        if element_name is None:
            self._action_chain.click(None)
        else:
            element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.click(element)

    def left_click_and_hold(self, on_element: WebElement = None):
        self._action_chain.click_and_hold(on_element)

    def left_click_and_hold_with_test_object(self, element_name: str = None):
        if element_name is None:
            self._action_chain.click_and_hold(None)
        else:
            element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.click_and_hold(element)

    def right_click(self, on_element: WebElement = None):
        self._action_chain.context_click(on_element)

    def right_click_with_test_object(self, element_name: str = None):
        if element_name is None:
            self._action_chain.context_click(None)
        else:
            element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.context_click(element)

    def left_double_click(self, on_element: WebElement = None):
        self._action_chain.double_click(on_element)

    def left_double_click_with_test_object(self, element_name: str = None):
        if element_name is None:
            self._action_chain.double_click(None)
        else:
            web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.double_click(web_element_wrapper.current_web_element)

    def release(self, on_element: WebElement = None):
        self._action_chain.release(on_element)

    def release_with_test_object(self, element_name: str = None):
        if element_name is None:
            self._action_chain.release(None)
        else:
            web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.release(web_element_wrapper.current_web_element)

    def press_key(self, keycode_on_key_class, on_element: WebElement = None):
        self._action_chain.key_down(keycode_on_key_class, on_element)

    def press_key_with_test_object(self, keycode_on_key_class, element_name: str = None):
        if element_name is None:
            self._action_chain.key_down(keycode_on_key_class, None)
        else:
            web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.key_down(keycode_on_key_class, web_element_wrapper.current_web_element)

    def release_key(self, keycode_on_key_class, on_element: WebElement = None):
        self._action_chain.key_up(keycode_on_key_class, on_element)

    def release_key_with_test_object(self, keycode_on_key_class, element_name: str = None):
        if element_name is None:
            self._action_chain.key_up(keycode_on_key_class, None)
        else:
            web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.key_up(keycode_on_key_class, web_element_wrapper.current_web_element)

    def move_by_offset(self, x: int, y: int):
        self._action_chain.move_by_offset(x, y)

    def pause(self, seconds: int):
        self._action_chain.pause(seconds)

    def send_keys(self, keys_to_send):
        self._action_chain.send_keys(*keys_to_send)

    def send_keys_to_element(self, element: WebElement, keys_to_send):
        self._action_chain.send_keys_to_element(element, *keys_to_send)

    def send_keys_to_element_with_test_object(self, element_name: str, keys_to_send):
        web_element_wrapper.current_web_element = self.current_webdriver.find_element(
            test_object_record.test_object_record_dict.get(element_name).test_object_type,
            test_object_record.test_object_record_dict.get(element_name).test_object_name
        )
        self._action_chain.send_keys_to_element(web_element_wrapper.current_web_element, *keys_to_send)

    def scroll(self, x: int, y: int, delta_x: int, delta_y: int, duration: int = 0, origin: str = "viewport"):
        self._action_chain.scroll(x, y, delta_x, delta_y, duration, origin)

    # webdriver wrapper add function
    def check_current_webdriver(self, check_dict: dict):
        check_webdriver(self.current_webdriver, check_dict)

    # window
    def maximize_window(self) -> None:
        self.current_webdriver.maximize_window()

    def fullscreen_window(self) -> None:
        self.current_webdriver.fullscreen_window()

    def minimize_window(self) -> None:
        self.current_webdriver.minimize_window()

    def set_window_size(self, width, height, window_handle='current') -> dict:
        return self.current_webdriver.set_window_size(width, height, window_handle)

    def set_window_position(self, x, y, window_handle='current') -> dict:
        return self.current_webdriver.set_window_position(x, y, window_handle)

    def get_window_position(self, window_handle='current') -> dict:
        return self.current_webdriver.get_window_position(window_handle)

    def get_window_rect(self) -> dict:
        return self.current_webdriver.get_window_rect()

    def set_window_rect(self, x=None, y=None, width=None, height=None) -> dict:
        return self.current_webdriver.set_window_rect(x, y, width, height)

    # save as file
    def get_screenshot_as_png(self) -> bytes:
        return self.current_webdriver.get_screenshot_as_png()

    def get_screenshot_as_base64(self) -> str:
        return self.current_webdriver.get_screenshot_as_base64()

    # log
    def get_log(self, log_type):
        return self.current_webdriver.get_log

    # close event

    def quit(self):
        test_object_record.clean_record()
        self._action_chain = None
        self.current_webdriver.quit()


webdriver_wrapper = WebDriverWrapper()
