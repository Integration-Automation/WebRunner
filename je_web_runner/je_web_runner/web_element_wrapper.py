from sys import stderr
from typing import List

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select

from je_web_runner.utils.assert_value.result_check import check_web_element
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class WebElementWrapper(object):

    def __init__(self):
        self.current_web_element: [WebElement] = None
        self.current_web_element_list: [List[WebElement]] = None

    def submit(self) -> None:
        """
        current web element submit
        :return: None
        """
        try:
            self.current_web_element.submit()
            record_action_to_list("Web element submit", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element submit", None, error)

    def clear(self) -> None:
        """
        current web element clear
        :return: None
        """
        try:
            self.current_web_element.clear()
            record_action_to_list("Web element clear", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element clear", None, error)

    def get_property(self, name: str) -> str:
        """
        :param name: name of property
        :return: property value as str
        """
        param = locals()
        try:
            record_action_to_list("Web element get_property", param, None)
            return self.current_web_element.get_property(name)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element get_property", param, error)

    def get_dom_attribute(self, name: str) -> str:
        """
        :param name: name of dom
        :return: dom attribute value as str
        """
        param = locals()
        try:
            record_action_to_list("Web element get_dom_attribute", param, None)
            return self.current_web_element.get_dom_attribute(name)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element get_dom_attribute", param, error)

    def get_attribute(self, name: str) -> str:
        """
        :param name: name of web element
        :return:web element attribute value as str
        """
        param = locals()
        try:
            record_action_to_list("Web element get_attribute", param, None)
            return self.current_web_element.get_attribute(name)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element get_attribute", param, error)

    def is_selected(self) -> bool:
        """
        check current web element is selected or not
        :return: True or False
        """
        try:
            record_action_to_list("Web element is_selected", None, None)
            return self.current_web_element.is_selected()
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element is_selected", None, error)

    def is_enabled(self) -> bool:
        """
        check current web element is enable or not
        :return: True or False
        """
        try:
            record_action_to_list("Web element is_enabled", None, None)
            return self.current_web_element.is_enabled()
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element is_enabled", None, error)

    def input_to_element(self, input_value: str) -> None:
        """
        input value to current web element
        :param input_value: what value we want to input to current web element
        :return: None
        """
        param = locals()
        try:
            self.current_web_element.send_keys(input_value)
            record_action_to_list("Web element input_to_element", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element input_to_element", param, error)

    def click_element(self) -> None:
        """
        click current web element
        :return: None
        """
        try:
            self.current_web_element.click()
            record_action_to_list("Web element click_element", None, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element click_element", None, error)

    def is_displayed(self) -> bool:
        """
        check current web element is displayed or not
        :return: True or False
        """
        try:
            record_action_to_list("Web element is_displayed", None, None)
            return self.current_web_element.is_displayed()
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element is_displayed", None, error)

    def value_of_css_property(self, property_name: str) -> str:
        """
        :param property_name: name of property
        :return: css property value as str
        """
        param = locals()
        try:
            record_action_to_list("Web element value_of_css_property", param, None)
            return self.current_web_element.value_of_css_property(property_name)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element value_of_css_property", param, error)

    def screenshot(self, filename: str) -> bool:
        """
        :param filename: full file name not need .png extension
        :return: Save True or not
        """
        param = locals()
        try:
            record_action_to_list("Web element screenshot", param, None)
            return self.current_web_element.screenshot(filename + ".png")
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element screenshot", param, error)

    # Web element wrapper add function
    def change_web_element(self, element_index: int) -> None:
        """
        :param element_index: change to web element index
        :return: web element list [element_index]
        """
        param = locals()
        try:
            self.current_web_element = self.current_web_element_list[element_index]
            record_action_to_list("Web element change_web_element", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element change_web_element", param, error)

    def check_current_web_element(self, check_dict: dict) -> None:
        """
        :param check_dict: check web element dict {name: should be value}
        :return: None
        """
        param = locals()
        try:
            check_web_element(self.current_web_element, check_dict)
            record_action_to_list("Web element check_current_web_element", param, None)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element check_current_web_element", param, error)

    def get_select(self) -> Select:
        """
        get Select(current web element)
        :return: Select(current web element)
        """
        try:
            record_action_to_list("Web element get_select", None, None)
            return Select(self.current_web_element)
        except Exception as error:
            print(repr(error), file=stderr)
            record_action_to_list("Web element get_select", None, error)


# use this wrapper to use web element
web_element_wrapper = WebElementWrapper()
