from typing import List

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select

from je_web_runner.utils.assert_value.result_check import check_web_element
from je_web_runner.utils.test_record.test_record import record_action_to_list


class WebElementWrapper(object):

    def __init__(self):
        self.current_web_element: [WebElement] = None
        self.current_web_element_list: [List[WebElement]] = None

    def input_to_element(self, input_value) -> None:
        self.current_web_element.send_keys(input_value)

    def click_element(self) -> None:
        self.current_web_element.click()

    def change_web_element(self, element_index: int) -> None:
        self.current_web_element = self.current_web_element_list[element_index]

    def check_current_web_element(self, check_dict: dict) -> None:
        check_web_element(self.current_web_element, check_dict)

    def get_select(self) -> Select:
        return Select(self.current_web_element)


web_element_wrapper = WebElementWrapper()
