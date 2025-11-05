from typing import List, Union

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select

from je_web_runner.utils.assert_value.result_check import check_web_element_details
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class WebElementWrapper(object):
    def __init__(self):
        # 當前操作的單一 WebElement
        # Current active WebElement
        self.current_web_element: Union[WebElement, None] = None

        # 當前操作的 WebElement 清單
        # Current list of WebElements
        self.current_web_element_list: Union[List[WebElement], None] = None

    def submit(self) -> None:
        """
        提交當前 WebElement
        Submit the current WebElement
        """
        web_runner_logger.info("WebElementWrapper submit")
        try:
            self.current_web_element.submit()
            record_action_to_list("Web element submit", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebElementWrapper submit, failed: {repr(error)}")
            record_action_to_list("Web element submit", None, error)

    def clear(self) -> None:
        """
        清除當前 WebElement 的內容
        Clear the content of the current WebElement
        """
        web_runner_logger.info("WebElementWrapper clear")
        try:
            self.current_web_element.clear()
            record_action_to_list("Web element clear", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebElementWrapper clear, failed: {repr(error)}")
            record_action_to_list("Web element clear", None, error)

    def get_property(self, name: str) -> None | str | bool | WebElement | dict:
        """
        取得 WebElement 的屬性
        Get property of the WebElement
        :param name: 屬性名稱 / property name
        :return: 屬性值 / property value
        """
        web_runner_logger.info(f"WebElementWrapper get_property, name: {name}")
        param = locals()
        try:
            record_action_to_list("Web element get_property", param, None)
            return self.current_web_element.get_property(name)
        except Exception as error:
            web_runner_logger.error(f"WebElementWrapper get_property, name: {name}, failed: {repr(error)}")
            record_action_to_list("Web element get_property", param, error)

    def get_dom_attribute(self, name: str) -> str | None:
        """
        取得 DOM 屬性
        Get DOM attribute
        :param name: DOM 屬性名稱 / DOM attribute name
        :return: 屬性值 / attribute value
        """
        web_runner_logger.info(f"WebElementWrapper get_dom_attribute, name: {name}")
        param = locals()
        try:
            record_action_to_list("Web element get_dom_attribute", param, None)
            return self.current_web_element.get_dom_attribute(name)
        except Exception as error:
            web_runner_logger.error(f"WebElementWrapper get_dom_attribute, name: {name}, failed: {repr(error)}")
            record_action_to_list("Web element get_dom_attribute", param, error)

    def get_attribute(self, name: str) -> str | None:
        """
        取得 WebElement 的屬性
        Get attribute of the WebElement
        :param name: 屬性名稱 / attribute name
        :return: 屬性值 / attribute value
        """
        web_runner_logger.info(f"WebElementWrapper get_attribute, name: {name}")
        param = locals()
        try:
            record_action_to_list("Web element get_attribute", param, None)
            return self.current_web_element.get_attribute(name)
        except Exception as error:
            web_runner_logger.error(f"WebElementWrapper get_attribute, name: {name}, failed: {repr(error)}")
            record_action_to_list("Web element get_attribute", param, error)

    def is_selected(self) -> bool | None:
        """
        檢查 WebElement 是否被選取
        Check if WebElement is selected
        :return: True/False
        """
        web_runner_logger.info("WebElementWrapper is_selected")
        try:
            record_action_to_list("Web element is_selected", None, None)
            return self.current_web_element.is_selected()
        except Exception as error:
            web_runner_logger.error(f"WebElementWrapper is_selected, failed: {repr(error)}")
            record_action_to_list("Web element is_selected", None, error)

    def is_enabled(self) -> bool | None:
        """
        檢查 WebElement 是否可用
        Check if WebElement is enabled
        :return: True/False
        """
        web_runner_logger.info("WebElementWrapper is_enabled")
        try:
            record_action_to_list("Web element is_enabled", None, None)
            return self.current_web_element.is_enabled()
        except Exception as error:
            web_runner_logger.error(f"WebElementWrapper is_enabled, failed: {repr(error)}")
            record_action_to_list("Web element is_enabled", None, error)

    def input_to_element(self, input_value: str) -> None:
        """
        輸入文字到 WebElement
        Input text into WebElement
        :param input_value: 要輸入的文字 / text to input
        """
        web_runner_logger.info(f"WebElementWrapper input_to_element, input_value: {input_value}")
        param = locals()
        try:
            self.current_web_element.send_keys(input_value)
            record_action_to_list("Web element input_to_element", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebElementWrapper input_to_element, input_value: {input_value}, failed: {repr(error)}")
            record_action_to_list("Web element input_to_element", param, error)

    def click_element(self) -> None:
        """
        點擊 WebElement
        Click the WebElement
        """
        web_runner_logger.info("WebElementWrapper click_element")
        try:
            self.current_web_element.click()
            record_action_to_list("Web element click_element", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebElementWrapper click_element, failed: {repr(error)}")
            record_action_to_list("Web element click_element", None, error)

    def is_displayed(self) -> bool | None:
        """
        檢查 WebElement 是否顯示
        Check if WebElement is displayed
        :return: True/False
        """
        web_runner_logger.info("WebElementWrapper is_displayed")
        try:
            record_action_to_list("Web element is_displayed", None, None)
            return self.current_web_element.is_displayed()
        except Exception as error:
            web_runner_logger.error(f"WebElementWrapper is_displayed, failed: {repr(error)}")
            record_action_to_list("Web element is_displayed", None, error)

    def value_of_css_property(self, property_name: str) -> str | None:
        """
        取得 CSS 屬性值
        Get CSS property value
        :param property_name: 屬性名稱 / property name
        :return: 屬性值 / property value
        """
        web_runner_logger.info(f"WebElementWrapper value_of_css_property, property_name: {property_name}")
        param = locals()
        try:
            record_action_to_list("Web element value_of_css_property", param, None)
            return self.current_web_element.value_of_css_property(property_name)
        except Exception as error:
            web_runner_logger.error(
                f"WebElementWrapper value_of_css_property, property_name: {property_name}, failed: {repr(error)}")
            record_action_to_list("Web element value_of_css_property", param, error)

    def screenshot(self, filename: str) -> bool | None:
        """
        對 WebElement 截圖並存檔
        Take screenshot of WebElement and save
        :param filename: 檔名 (不需加 .png) / filename (without .png)
        :return: 是否成功 / True if success
        """
        web_runner_logger.info(f"WebElementWrapper screenshot, filename: {filename}")
        param = locals()
        try:
            record_action_to_list("Web element screenshot", param, None)
            return self.current_web_element.screenshot(filename + ".png")
        except Exception as error:
            web_runner_logger.info(f"WebElementWrapper screenshot, filename: {filename}, failed: {repr(error)}")
            record_action_to_list("Web element screenshot", param, error)

    def change_web_element(self, element_index: int) -> None:
        """
        切換當前 WebElement
        Change current WebElement
        :param element_index: WebElement 清單索引 / index in WebElement list
        """
        web_runner_logger.info(f"WebElementWrapper change_web_element, element_index: {element_index}")
        param = locals()
        try:
            self.current_web_element = self.current_web_element_list[element_index]
            record_action_to_list("Web element change_web_element", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebElementWrapper change_web_element, element_index: {element_index}, failed: {repr(error)}")
            record_action_to_list("Web element change_web_element", param, error)

    def check_current_web_element(self, check_dict: dict) -> None:
        """
        檢查當前 WebElement 是否符合指定條件
        Check if the current WebElement matches the given conditions

        :param check_dict: 驗證用的字典 {屬性名稱: 預期值}
                           Dictionary for validation {attribute_name: expected_value}
        :return: None
        """
        web_runner_logger.info(f"WebElementWrapper check_current_web_element, check_dict: {check_dict}")
        param = locals()
        try:
            # 呼叫工具函式檢查 WebElement 的屬性
            # Call utility function to check WebElement details
            check_web_element_details(self.current_web_element, check_dict)

            # 紀錄成功動作
            # Record successful action
            record_action_to_list("Web element check_current_web_element", param, None)
        except Exception as error:
            # 錯誤處理與紀錄
            # Handle and log error
            web_runner_logger.error(
                f"WebElementWrapper check_current_web_element, check_dict: {check_dict}, failed: {repr(error)}"
            )
            record_action_to_list("Web element check_current_web_element", param, error)

    def get_select(self) -> Select | None:
        """
        取得 Select 物件 (用於操作下拉選單)
        Get a Select object (for handling dropdown menus)

        :return: Select(current web element) 或 None
                 Select(current web element) or None
        """
        web_runner_logger.info("WebElementWrapper get_select")
        try:
            # 紀錄成功動作
            # Record successful action
            record_action_to_list("Web element get_select", None, None)

            # 回傳 Select 包裝的 WebElement
            # Return Select wrapper of the WebElement
            return Select(self.current_web_element)
        except Exception as error:
            # 錯誤處理與紀錄
            # Handle and log error
            web_runner_logger.error(f"WebElementWrapper get_select, failed: {repr(error)}")
            record_action_to_list("Web element get_select", None, error)


# 使用此包裝器來操作 WebElement
# Use this wrapper to operate on WebElement
web_element_wrapper = WebElementWrapper()