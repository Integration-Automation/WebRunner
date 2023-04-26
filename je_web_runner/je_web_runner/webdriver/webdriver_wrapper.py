import typing
from sys import stderr
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

from je_web_runner.je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.je_web_runner.webdriver.webdriver_with_options import set_webdriver_options_capability_wrapper
from je_web_runner.utils.assert_value.result_check import check_webdriver_details
from je_web_runner.utils.exception.exception_tags import selenium_wrapper_web_driver_not_found_error
from je_web_runner.utils.exception.exceptions import WebRunnerException, WebRunnerWebDriverIsNoneException
from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverNotFoundException
from je_web_runner.utils.test_object.test_object_class import TestObject
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.test_record.test_record_class import record_action_to_list
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.microsoft import IEDriverManager
from webdriver_manager.chrome import ChromeType

_webdriver_dict = {
    "chrome": webdriver.Chrome,
    "chromium": webdriver.Chrome,
    "firefox": webdriver.Firefox,
    "edge": webdriver.Edge,
    "ie": webdriver.Ie,
    "safari": webdriver.Safari,
}

_webdriver_manager_dict = {
    "chrome": ChromeDriverManager,
    "chromium": ChromeDriverManager(chrome_type=ChromeType.CHROMIUM),
    "firefox": GeckoDriverManager,
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

    def set_driver(self, webdriver_name: str,
                   webdriver_manager_option_dict: dict = None, **kwargs) -> \
            Union[
                webdriver.Chrome,
                webdriver.Chrome,
                webdriver.Firefox,
                webdriver.Edge,
                webdriver.Ie,
                webdriver.Safari,
            ]:
        """
        :param webdriver_name: which webdriver we want to use
        :param webdriver_manager_option_dict: if you want to set webdriver download manager
        :param kwargs: used to catch var
        :return: current use webdriver
        """
        param = locals()
        try:
            webdriver_name = str(webdriver_name).lower()
            webdriver_value = _webdriver_dict.get(webdriver_name)
            if webdriver_value is None:
                raise WebRunnerWebDriverNotFoundException(selenium_wrapper_web_driver_not_found_error)
            webdriver_install_manager = _webdriver_manager_dict.get(webdriver_name)
            if webdriver_manager_option_dict is None:
                webdriver_service = _webdriver_service_dict.get(webdriver_name)(
                    webdriver_install_manager().install(),
                )
            else:
                webdriver_service = _webdriver_service_dict.get(webdriver_name)(
                    webdriver_install_manager(**webdriver_manager_option_dict).install(),
                )
            self.current_webdriver = webdriver_value(service=webdriver_service, **kwargs)
            self._webdriver_name = webdriver_name
            self._action_chain = ActionChains(self.current_webdriver)
            record_action_to_list("webdriver wrapper set_driver", param, None)
            return self.current_webdriver
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper set_driver", param, error)
            raise WebRunnerException

    def set_webdriver_options_capability(self, key_and_vale_dict: dict) -> \
            Union[
                webdriver.Chrome,
                webdriver.Chrome,
                webdriver.Firefox,
                webdriver.Edge,
                webdriver.Ie,
                webdriver.Safari,
            ]:
        """
        :param key_and_vale_dict: use to set webdriver capability
        :return: current webdriver
        """
        param = locals()
        try:
            if self._webdriver_name is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            record_action_to_list("webdriver wrapper set_webdriver_options_capability", param, None)
            return set_webdriver_options_capability_wrapper(self._webdriver_name, key_and_vale_dict)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper set_webdriver_options_capability", param, error)
            raise WebRunnerException

    # web element
    def find_element(self, test_object: TestObject) -> WebElement:
        """
        :param test_object: use test object to find element
        :return: fined web element
        """
        param = locals()
        try:
            if self.current_webdriver is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                test_object.test_object_type, test_object.test_object_name)
            return web_element_wrapper.current_web_element
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper find_element", param, error)

    def find_elements(self, test_object: TestObject) -> List[WebElement]:
        """
        :param test_object: use test object to find elements
        :return: list include fined web element
        """
        param = locals()
        try:
            if self.current_webdriver is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            web_element_wrapper.current_web_element_list = self.current_webdriver.find_elements(
                test_object.test_object_type, test_object.test_object_name)
            record_action_to_list("webdriver wrapper find_elements", param, None)
            return web_element_wrapper.current_web_element_list
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper find_elements", param, error)

    def find_element_with_test_object_record(self, element_name: str) -> WebElement:
        """
        this is executor use but still can normally use
        :param element_name: test object name
        :return: fined web element
        """
        param = locals()
        try:
            if self.current_webdriver is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            record_action_to_list("webdriver wrapper find_element_with_test_object_record", param, None)
            return web_element_wrapper.current_web_element
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper find_element_with_test_object_record", param, error)

    def find_elements_with_test_object_record(self, element_name: str) -> List[WebElement]:
        """
        this is executor use but still can normally use
        :param element_name: test object name
        :return: list include fined web element
        """
        param = locals()
        try:
            if self.current_webdriver is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            web_element_wrapper.current_web_element_list = self.current_webdriver.find_elements(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            record_action_to_list("webdriver wrapper find_elements_with_test_object_record", param, None)
            return web_element_wrapper.current_web_element
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper find_elements_with_test_object_record", param, error)

    # wait
    def implicitly_wait(self, time_to_wait: int) -> None:
        """
        selenium implicitly_wait
        :param time_to_wait: how much time we want to wait
        :return: None
        """
        param = locals()
        try:
            self.current_webdriver.implicitly_wait(time_to_wait)
            record_action_to_list("webdriver wrapper implicitly_wait", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper implicitly_wait", param, error)

    def explict_wait(self, wait_time: int, method: typing.Callable, until_type: bool = True):
        """
        selenium explict_wait
        :param wait_time: how much time we want to wait if over-time will raise an exception
        :param method: a program statement should be return True or False
        :param until_type: what type until wait True is until False is until_not
        :return:
        """
        param = locals()
        try:
            if until_type:
                record_action_to_list("webdriver wrapper explict_wait", param, None)
                return WebDriverWait(self.current_webdriver, wait_time).until(method)
            else:
                record_action_to_list("webdriver wrapper explict_wait", param, None)
                return WebDriverWait(self.current_webdriver, wait_time).until_not(method)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper explict_wait", param, error)

    # webdriver url redirect

    def to_url(self, url: str) -> None:
        """
        to url
        :param url: what url we want redirect to
        :return: None
        """
        param = locals()
        try:
            self.current_webdriver.get(url)
            record_action_to_list("webdriver wrapper to_url", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper to_url", param, error)

    def forward(self) -> None:
        """
        forward current page
        :return: None
        """
        try:
            self.current_webdriver.forward()
            record_action_to_list("webdriver wrapper forward", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper forward", None, error)

    def back(self) -> None:
        """
        back current page
        :return: None
        """
        try:
            self.current_webdriver.back()
            record_action_to_list("webdriver wrapper back", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper back", None, error)

    def refresh(self) -> None:
        """
        refresh current page
        :return: None
        """
        try:
            self.current_webdriver.refresh()
            record_action_to_list("webdriver wrapper refresh", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper refresh", None, error)

    # webdriver new page
    def switch(self, switch_type: str, switch_target_name: str = None):
        """
        switch to target element
        :param switch_type: what type switch? one of  [active_element, default_content, frame,
        parent_frame, window, alert]
        :param switch_target_name: what target we want to switch use name to search
        :return: what we switch to
        """
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
                switch_type_dict.update(
                    {"alert": self.current_webdriver.switch_to.alert}
                )
            except NoAlertPresentException as error:
                switch_type_dict.update(
                    {"alert": None}
                )
                print(repr(error), file=stderr)
            if switch_type in ["active_element", "alert"]:
                record_action_to_list("webdriver wrapper switch", param, None)
                return switch_type_dict.get(switch_type)
            elif switch_type in ["default_content", "parent_frame"]:
                record_action_to_list("webdriver wrapper switch", param, None)
                return switch_type_dict.get(switch_type)()
            else:
                record_action_to_list("webdriver wrapper switch", param, None)
                return switch_type_dict.get(switch_type)(switch_target_name)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper switch", param, error)

    # timeout
    def set_script_timeout(self, time_to_wait: int) -> None:
        """
        set max script execute time
        :param time_to_wait: how much time we want to wait if over-time will raise an exception
        :return: None
        """
        param = locals()
        try:
            self.current_webdriver.set_script_timeout(time_to_wait)
            record_action_to_list("webdriver wrapper set_script_timeout", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper set_script_timeout", param, error)

    def set_page_load_timeout(self, time_to_wait: int) -> None:
        """
        set page load max wait time
        :param time_to_wait: how much time we want to wait if over-time will raise an exception
        :return: None
        """
        param = locals()
        try:
            self.current_webdriver.set_page_load_timeout(time_to_wait)
            record_action_to_list("webdriver wrapper set_page_load_timeout", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper set_page_load_timeout", param, error)

    # cookie
    def get_cookies(self) -> List[dict]:
        """
        get current page cookies
        :return: cookies as list
        """
        try:
            record_action_to_list("webdriver wrapper get_cookies", None, None)
            return self.current_webdriver.get_cookies()
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper get_cookies", None, error)

    def get_cookie(self, name: str) -> dict:
        """
        use to get current page cookie
        :param name: use cookie name to find cookie
        :return: {cookie_name: value}
        """
        param = locals()
        try:
            record_action_to_list("webdriver wrapper get_cookie", param, None)
            return self.current_webdriver.get_cookie(name)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper get_cookie", param, error)

    def add_cookie(self, cookie_dict: dict) -> None:
        """
        use to add cookie to current page
        :param cookie_dict: {cookie_name: value}
        :return: None
        """
        param = locals()
        try:
            self.current_webdriver.add_cookie(cookie_dict)
            record_action_to_list("webdriver wrapper add_cookie", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper add_cookie", param, error)

    def delete_cookie(self, name) -> None:
        """
        use to delete current page cookie
        :param name: use name to find cookie
        :return: None
        """
        param = locals()
        try:
            self.current_webdriver.delete_cookie(name)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper delete_cookie", param, error)

    def delete_all_cookies(self) -> None:
        """
        delete current page all cookies
        :return: None
        """
        try:
            self.current_webdriver.delete_all_cookies()
            record_action_to_list("webdriver wrapper delete_all_cookies", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper delete_all_cookies", None, error)

    # exec selenium command
    def execute(self, driver_command: str, params: dict = None) -> dict:
        """
        :param driver_command: webdriver command
        :param params: webdriver command params
        :return: after execute dict
        """
        param = locals()
        try:
            record_action_to_list("webdriver wrapper execute", param, None)
            return self.current_webdriver.execute(driver_command, params)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper execute", param, error)

    def execute_script(self, script: str, *args) -> None:
        """
        execute script
        :param script: script to execute
        :param args: script args
        :return: None
        """
        param = locals()
        try:
            self.current_webdriver.execute_script(script, *args)
            record_action_to_list("webdriver wrapper execute_script", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper execute_script", param, error)

    def execute_async_script(self, script: str, *args):
        """
        execute script async
        :param script:script to execute
        :param args: script args
        :return: None
        """
        param = locals()
        try:
            self.current_webdriver.execute_async_script(script, *args)
            record_action_to_list("webdriver wrapper execute_async_script", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper execute_async_script", param, error)

    # ActionChains
    def move_to_element(self, targe_element: WebElement) -> None:
        """
        move mouse to target web element
        :param targe_element: target web element
        :return: None
        """
        param = locals()
        try:
            self._action_chain.move_to_element(targe_element)
            record_action_to_list("webdriver wrapper move_to_element", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper move_to_element", param, error)

    def move_to_element_with_test_object(self, element_name: str):
        """
        move mouse to target web element use test object
        :param element_name: test object name
        :return: None
        """
        param = locals()
        try:
            element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.move_to_element(element)
            record_action_to_list("webdriver wrapper move_to_element_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper move_to_element_with_test_object", param, error)

    def move_to_element_with_offset(self, target_element: WebElement, offset_x: int, offset_y: int) -> None:
        """
        move to target element with offset
        :param target_element: what target web element we want to move to
        :param offset_x: offset x
        :param offset_y: offset y
        :return: None
        """
        param = locals()
        try:
            self._action_chain.move_to_element_with_offset(target_element, offset_x, offset_y)
            record_action_to_list("webdriver wrapper move_to_element_with_offset", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper move_to_element_with_offset", param, error)

    def move_to_element_with_offset_and_test_object(self, element_name: str, offset_x: int, offset_y: int) -> None:
        """
        move to target element with offset use test object
        :param element_name: test object name
        :param offset_x: offset x
        :param offset_y: offset y
        :return: None
        """
        param = locals()
        try:
            element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.move_to_element_with_offset(element, offset_x, offset_y)
            record_action_to_list("webdriver wrapper move_to_element_with_offset_and_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper move_to_element_with_offset_and_test_object", param, error)

    def drag_and_drop(self, web_element: WebElement, targe_element: WebElement) -> None:
        """
        drag web element to target element then drop
        :param web_element: which web element we want to drag and drop
        :param targe_element: target web element to drop
        :return: None
        """
        param = locals()
        try:
            self._action_chain.drag_and_drop(web_element, targe_element)
            record_action_to_list("webdriver wrapper drag_and_drop", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper drag_and_drop", param, error)

    def drag_and_drop_with_test_object(self, element_name: str, target_element_name: str):
        """
        drag web element to target element then drop use testobject
        :param element_name: which web element we want to drag and drop use name to find
        :param target_element_name: target web element to drop use name to find
        :return: None
        """
        param = locals()
        try:
            element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            another_element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(target_element_name).test_object_type,
                test_object_record.test_object_record_dict.get(target_element_name).test_object_name
            )
            self._action_chain.drag_and_drop(element, another_element)
            record_action_to_list("webdriver wrapper drag_and_drop_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper drag_and_drop_with_test_object", param, error)

    def drag_and_drop_offset(self, web_element: WebElement, target_x: int, target_y: int) -> None:
        """
        drag web element to target element then drop with offset
        :param web_element: which web element we want to drag and drop with offset
        :param target_x: offset x
        :param target_y: offset y
        :return: None
        """
        param = locals()
        try:
            self._action_chain.drag_and_drop_by_offset(web_element, target_x, target_y)
            record_action_to_list("webdriver wrapper drag_and_drop_offset", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper drag_and_drop_offset", param, error)

    def drag_and_drop_offset_with_test_object(self, element_name: str, offset_x: int, offset_y: int) -> None:
        """
        drag web element to target element then drop with offset and test object
        :param element_name: test object name
        :param offset_x: offset x
        :param offset_y: offset y
        :return: None
        """
        param = locals()
        try:
            element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.drag_and_drop_by_offset(element, offset_x, offset_y)
            record_action_to_list("webdriver wrapper drag_and_drop_offset_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper drag_and_drop_offset_with_test_object", param, error)

    def perform(self) -> None:
        """
        perform actions
        :return: None
        """
        try:
            self._action_chain.perform()
            record_action_to_list("webdriver wrapper perform", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper perform", None, error)

    def reset_actions(self) -> None:
        """
        clear actions
        :return: None
        """
        try:
            self._action_chain.reset_actions()
            record_action_to_list("webdriver wrapper reset_actions", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper reset_actions", None, error)

    def left_click(self, on_element: WebElement = None) -> None:
        """
        left click mouse on current mouse position or click on web element
        :param on_element: can be None or web element
        :return: None
        """
        param = locals()
        try:
            self._action_chain.click(on_element)
            record_action_to_list("webdriver wrapper left_click", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper left_click", param, error)

    def left_click_with_test_object(self, element_name: str = None) -> None:
        """
        left click mouse on current mouse position or click on web element
        find use test object name
        :param element_name: test object name
        :return: None
        """
        param = locals()
        try:
            if element_name is None:
                self._action_chain.click(None)
            else:
                element = self.current_webdriver.find_element(
                    test_object_record.test_object_record_dict.get(element_name).test_object_type,
                    test_object_record.test_object_record_dict.get(element_name).test_object_name
                )
                self._action_chain.click(element)
                record_action_to_list("webdriver wrapper left_click_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper left_click_with_test_object", param, error)

    def left_click_and_hold(self, on_element: WebElement = None) -> None:
        """
        left click and hold on current mouse position or left click and hold on web element
        :param on_element: can be None or web element
        :return: None
        """
        param = locals()
        try:
            self._action_chain.click_and_hold(on_element)
            record_action_to_list("webdriver wrapper left_click_and_hold", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper left_click_and_hold", param, error)

    def left_click_and_hold_with_test_object(self, element_name: str = None) -> None:
        """
        left click and hold on current mouse position or left click and hold on web element
        find use test object name
        :param element_name: test object name
        :return: None
        """
        param = locals()
        try:
            if element_name is None:
                self._action_chain.click_and_hold(None)
            else:
                element = self.current_webdriver.find_element(
                    test_object_record.test_object_record_dict.get(element_name).test_object_type,
                    test_object_record.test_object_record_dict.get(element_name).test_object_name
                )
                self._action_chain.click_and_hold(element)
            record_action_to_list("webdriver wrapper left_click_and_hold_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper left_click_and_hold_with_test_object", param, error)

    def right_click(self, on_element: WebElement = None) -> None:
        """
        right click mouse on current mouse position or click on web element
        :param on_element: can be None or web element
        :return: None
        """
        param = locals()
        try:
            self._action_chain.context_click(on_element)
            record_action_to_list("webdriver wrapper right_click", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper right_click", param, error)

    def right_click_with_test_object(self, element_name: str = None) -> None:
        """
        right click mouse on current mouse position or click on web element
        find use test object name
        :param element_name: test object name
        :return: None
        """
        param = locals()
        try:
            if element_name is None:
                self._action_chain.context_click(None)
            else:
                element = self.current_webdriver.find_element(
                    test_object_record.test_object_record_dict.get(element_name).test_object_type,
                    test_object_record.test_object_record_dict.get(element_name).test_object_name
                )
                self._action_chain.context_click(element)
            record_action_to_list("webdriver wrapper right_click_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper right_click_with_test_object", param, error)

    def left_double_click(self, on_element: WebElement = None) -> None:
        """
        double left click mouse on current mouse position or double click on web element
        :param on_element: can be None or web element
        :return: None
        """
        param = locals()
        try:
            self._action_chain.double_click(on_element)
            record_action_to_list("webdriver wrapper left_double_click", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper left_double_click", param, error)

    def left_double_click_with_test_object(self, element_name: str = None) -> None:
        """
        double left click mouse on current mouse position or double click on web element
        find use test object name
        :param element_name: test object name
        :return: None
        """
        param = locals()
        try:
            if element_name is None:
                self._action_chain.double_click(None)
            else:
                web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                    test_object_record.test_object_record_dict.get(element_name).test_object_type,
                    test_object_record.test_object_record_dict.get(element_name).test_object_name
                )
                self._action_chain.double_click(web_element_wrapper.current_web_element)
            record_action_to_list("webdriver wrapper left_double_click_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper left_double_click_with_test_object", param, error)

    def release(self, on_element: WebElement = None) -> None:
        """
        release mouse or web element
        :param on_element: can be None or web element
        :return: None
        """
        param = locals()
        try:
            self._action_chain.release(on_element)
            record_action_to_list("webdriver wrapper release", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper release", param, error)

    def release_with_test_object(self, element_name: str = None) -> None:
        """
        release mouse or web element find use test object name
        :param element_name: test object name
        :return: None
        """
        param = locals()
        try:
            if element_name is None:
                self._action_chain.release(None)
            else:
                web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                    test_object_record.test_object_record_dict.get(element_name).test_object_type,
                    test_object_record.test_object_record_dict.get(element_name).test_object_name
                )
                self._action_chain.release(web_element_wrapper.current_web_element)
            record_action_to_list("webdriver wrapper release_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper release_with_test_object", param, error)

    def press_key(self, keycode_on_key_class, on_element: WebElement = None) -> None:
        """
        press key or press key on web element key should be in Key
        :param keycode_on_key_class: which key code to press
        :param on_element: can be None or web element
        :return: None
        """
        param = locals()
        try:
            self._action_chain.key_down(keycode_on_key_class, on_element)
            record_action_to_list("webdriver wrapper press_key", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper press_key", param, error)

    def press_key_with_test_object(self, keycode_on_key_class, element_name: str = None) -> None:
        """
        press key or press key on web element key should be in Key find web element use test object name
        :param keycode_on_key_class: which key code to press
        :param element_name: test object name
        :return: None
        """
        param = locals()
        try:
            if element_name is None:
                self._action_chain.key_down(keycode_on_key_class, None)
            else:
                web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                    test_object_record.test_object_record_dict.get(element_name).test_object_type,
                    test_object_record.test_object_record_dict.get(element_name).test_object_name
                )
                self._action_chain.key_down(keycode_on_key_class, web_element_wrapper.current_web_element)
            record_action_to_list("webdriver wrapper press_key_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper press_key_with_test_object", param, error)

    def release_key(self, keycode_on_key_class, on_element: WebElement = None) -> None:
        """
        release key or release key on web element key should be in Key
        :param keycode_on_key_class: which key code to release
        :param on_element: can be None or web element
        :return: None
        """
        param = locals()
        try:
            self._action_chain.key_up(keycode_on_key_class, on_element)
            record_action_to_list("webdriver wrapper release_key", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper release_key", param, error)

    def release_key_with_test_object(self, keycode_on_key_class, element_name: str = None) -> None:
        """
        release key or release key on web element key should be in Key
        find use test object
        :param keycode_on_key_class: which key code to release
        :param element_name: test object name
        :return: None
        """
        param = locals()
        try:
            if element_name is None:
                self._action_chain.key_up(keycode_on_key_class, None)
            else:
                web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                    test_object_record.test_object_record_dict.get(element_name).test_object_type,
                    test_object_record.test_object_record_dict.get(element_name).test_object_name
                )
                self._action_chain.key_up(keycode_on_key_class, web_element_wrapper.current_web_element)
            record_action_to_list("webdriver wrapper release_key_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper release_key_with_test_object", param, error)

    def move_by_offset(self, offset_x: int, offset_y: int) -> None:
        """
        move mouse use offset
        :param offset_x: offset x
        :param offset_y: offset y
        :return: None
        """
        param = locals()
        try:
            self._action_chain.move_by_offset(offset_x, offset_y)
            record_action_to_list("webdriver wrapper move_by_offset", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper move_by_offset", param, error)

    def pause(self, seconds: int) -> None:
        """
        pause seconds time (this many be let selenium raise some exception)
        :param seconds: seconds to pause
        :return: None
        """
        param = locals()
        try:
            self._action_chain.pause(seconds)
            record_action_to_list("webdriver wrapper pause", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper pause", param, error)

    def send_keys(self, keys_to_send) -> None:
        """
        send(press and release) keyboard key
        :param keys_to_send: which key on keyboard we want to send
        :return: None
        """
        param = locals()
        try:
            self._action_chain.send_keys(*keys_to_send)
            record_action_to_list("webdriver wrapper send_keys", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper send_keys", param, error)

    def send_keys_to_element(self, element: WebElement, keys_to_send) -> None:
        """
        :param element: which element we want send key to
        :param keys_to_send:  which key on keyboard we want to send
        :return: None
        """
        param = locals()
        try:
            self._action_chain.send_keys_to_element(element, *keys_to_send)
            record_action_to_list("webdriver wrapper send_keys_to_element", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper send_keys_to_element", param, error)

    def send_keys_to_element_with_test_object(self, element_name: str, keys_to_send) -> None:
        """
        :param element_name: test object name
        :param keys_to_send:  which key on keyboard we want to send find use test object
        :return: None
        """
        param = locals()
        try:
            web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                test_object_record.test_object_record_dict.get(element_name).test_object_type,
                test_object_record.test_object_record_dict.get(element_name).test_object_name
            )
            self._action_chain.send_keys_to_element(web_element_wrapper.current_web_element, *keys_to_send)
            record_action_to_list("webdriver wrapper send_keys_to_element_with_test_object", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper send_keys_to_element_with_test_object", param, error)

    def scroll(self, scroll_x: int, scroll_y: int, delta_x: int, delta_y: int,
               duration: int = 0, origin: str = "viewport") -> None:
        """
        :param scroll_x: starting x coordinate
        :param scroll_y: starting y coordinate
        :param delta_x: the distance the mouse will scroll on the x axis
        :param delta_y: the distance the mouse will scroll on the y axis
        :param duration: delay to wheel
        :param origin: what is origin to scroll
        :return:
        """
        param = locals()
        try:
            self._action_chain.scroll(scroll_x, scroll_y, delta_x, delta_y, duration, origin)
            record_action_to_list("webdriver wrapper scroll", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper scroll", param, error)

    # window
    def maximize_window(self) -> None:
        """
        maximize current window
        :return: None
        """
        try:
            self.current_webdriver.maximize_window()
            record_action_to_list("webdriver wrapper maximize_window", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper maximize_window", None, error)

    def fullscreen_window(self) -> None:
        """
        full-screen current window
        :return: None
        """
        try:
            self.current_webdriver.fullscreen_window()
            record_action_to_list("webdriver wrapper fullscreen_window", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper fullscreen_window", None, error)

    def minimize_window(self) -> None:
        """
        minimize current window
        :return: None
        """
        try:
            self.current_webdriver.minimize_window()
            record_action_to_list("webdriver wrapper minimize_window", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper minimize_window", None, error)

    def set_window_size(self, width, height, window_handle='current') -> dict:
        """
        :param width: window width (pixel)
        :param height: window height (pixel)
        :param window_handle: normally is "current" (w3c)  if not "current" will make exception
        :return: size
        """
        param = locals()
        try:
            record_action_to_list("webdriver wrapper set_window_size", param, None)
            return self.current_webdriver.set_window_size(width, height, window_handle)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper set_window_size", param, error)

    def set_window_position(self, x, y, window_handle='current') -> dict:
        """
        :param x: position x
        :param y: position y
        :param window_handle: normally is "current" (w3c)  if not "current" will make exception
        :return: execute(Command.SET_WINDOW_RECT,
        {"x": x, "y": y, "width": width, "height": height})['value']
        """
        param = locals()
        try:
            record_action_to_list("webdriver wrapper set_window_position", param, None)
            return self.current_webdriver.set_window_position(x, y, window_handle)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper set_window_position", param, error)

    def get_window_position(self, window_handle='current') -> dict:
        """
        :param window_handle: normally is "current" (w3c)  if not "current" will make exception
        :return: window position dict
        """
        param = locals()
        try:
            record_action_to_list("webdriver wrapper get_window_position", param, None)
            return self.current_webdriver.get_window_position(window_handle)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper get_window_position", param, error)

    def get_window_rect(self) -> dict:
        """
        :return: execute(Command.GET_WINDOW_RECT)['value']
        """
        try:
            record_action_to_list("webdriver wrapper get_window_position", None, None)
            return self.current_webdriver.get_window_rect()
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper get_window_position", None, error)

    def set_window_rect(self, x: int = None, y: int = None, width: int = None, height: int = None) -> dict:
        """
        only supported for w3c compatible another browsers need use set_window_position or set_window_size
        :param x: set x coordinates
        :param y: set y coordinates
        :param width: set window width
        :param height: set window height
        :return: execute(Command.SET_WINDOW_RECT,
        {"x": x, "y": y, "width": width, "height": height})['value']
        """
        param = locals()
        try:
            record_action_to_list("webdriver wrapper set_window_rect", param, None)
            return self.current_webdriver.set_window_rect(x, y, width, height)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper set_window_rect", param, error)

    # save as file
    def get_screenshot_as_png(self) -> bytes:
        """
        get current page screenshot as png
        :return: screenshot as bytes
        """
        try:
            record_action_to_list("webdriver wrapper get_screenshot_as_png", None, None)
            return self.current_webdriver.get_screenshot_as_png()
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper get_screenshot_as_png", None, error)

    def get_screenshot_as_base64(self) -> str:
        """
        get current page screenshot as base64 str
        :return: screenshot as str
        """
        try:
            record_action_to_list("webdriver wrapper get_screenshot_as_base64", None, None)
            return self.current_webdriver.get_screenshot_as_base64()
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper get_screenshot_as_base64", None, error)

    # log
    def get_log(self, log_type: str):
        """
        :param log_type: ["browser", "driver", client", "server]
        :return: execute(Command.GET_LOG, {'type': log_type})['value']
        """
        try:
            record_action_to_list("webdriver wrapper get_log", None, None)
            return self.current_webdriver.get_log(log_type)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper get_log", None, error)

    # webdriver wrapper add function
    def check_current_webdriver(self, check_dict: dict) -> None:
        """
        if check failure will raise an exception
        :param check_dict: use to check current webdriver state
        :return: None
        """
        param = locals()
        try:
            check_webdriver_details(self.current_webdriver, check_dict)
            record_action_to_list("webdriver wrapper check_current_webdriver", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper check_current_webdriver", param, error)

    # close event
    def quit(self) -> None:
        """
        quit this webdriver
        :return: None
        """
        try:
            test_object_record.clean_record()
            self._action_chain = None
            record_action_to_list("webdriver wrapper quit", None, None)
            self.current_webdriver.quit()
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("webdriver wrapper quit", None, error)
            raise WebRunnerException


webdriver_wrapper = WebDriverWrapper()
