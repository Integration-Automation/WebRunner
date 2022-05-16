from typing import List

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select
from selenium.webdriver import ActionChains

from je_web_runner.utils.assert_value.result_check import check_web_element


class WebElementWrapper(object):

    def __init__(self):
        self.current_web_element: [WebElement] = None
        self.current_web_element_list: [List[WebElement]] = None

    def input_to_element(self, input_value):
        self.current_web_element.send_keys(input_value)

    def click_element(self):
        self.current_web_element.lef_click()

    def change_web_element(self, element_index: int):
        self.current_web_element = self.current_web_element_list[element_index]

    def check_current_web_element(self, check_dict: dict):
        check_web_element(self.current_web_element, check_dict)

    def get_select(self):
        return Select(self.current_web_element)


web_element_wrapper = WebElementWrapper()
