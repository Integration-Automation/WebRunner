from typing import Any, Union

from selenium.webdriver import DesiredCapabilities

from je_web_runner.utils.exception.exception_tags import selenium_wrapper_web_driver_not_found_error
from je_web_runner.utils.exception.exceptions import WebRunnerException

# 定義可用的 WebDriver 與其對應的 DesiredCapabilities
# Define available WebDrivers and their corresponding DesiredCapabilities
desired_capabilities_dict = {
    "firefox": DesiredCapabilities.FIREFOX,
    "chrome": DesiredCapabilities.CHROME,
    "edge": DesiredCapabilities.EDGE,
    "safari": DesiredCapabilities.SAFARI,
}


def get_desired_capabilities_keys() -> Union[str, Any]:
    """
    取得所有可用的 WebDriver 名稱
    Get all available WebDriver names

    :return: WebDriver 名稱清單 (dict_keys)
             Keys of available WebDrivers (dict_keys)
    """
    return desired_capabilities_dict.keys()


def get_desired_capabilities(webdriver_name: str) -> dict:
    """
    根據 WebDriver 名稱取得對應的 DesiredCapabilities
    Get DesiredCapabilities by WebDriver name

    :param webdriver_name: WebDriver 名稱 (firefox, chrome, edge, safari)
                           WebDriver name (firefox, chrome, edge, safari)
    :return: DesiredCapabilities (dict 格式)
             DesiredCapabilities (as dict)
    :raises WebRunnerException: 若名稱不存在於字典中
                                If webdriver_name is not found in dict
    """
    desired_capabilities = desired_capabilities_dict.get(webdriver_name)
    if desired_capabilities is None:
        raise WebRunnerException(selenium_wrapper_web_driver_not_found_error)
    return desired_capabilities.copy()