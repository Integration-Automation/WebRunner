from typing import Any, Union

from selenium.webdriver import DesiredCapabilities

from je_web_runner.utils.exception.exception_tag import selenium_wrapper_web_driver_not_found_error
from je_web_runner.utils.exception.exceptions import WebRunnerException

desired_capabilities_dict = {
    "firefox": DesiredCapabilities.FIREFOX,
    "chrome": DesiredCapabilities.CHROME,
    "edge": DesiredCapabilities.EDGE,
    "safari": DesiredCapabilities.SAFARI,
}


def get_desired_capabilities_keys() -> Union[str, Any]:
    """
    :return: return all webdriver you can get desired capabilities
    """
    return desired_capabilities_dict.keys()


def get_desired_capabilities(webdriver_name: str) -> \
        [
            DesiredCapabilities.FIREFOX.copy(),
            DesiredCapabilities.CHROME.copy(),
            DesiredCapabilities.EDGE.copy(),
            DesiredCapabilities.SAFARI.copy(),
        ]:
    """
    choose webdriver to get desired capabilities
    :param webdriver_name: name to get desired capabilities
    :return: desired capabilities
    """
    desired_capabilities = desired_capabilities_dict.get(webdriver_name)
    if desired_capabilities is None:
        raise WebRunnerException(selenium_wrapper_web_driver_not_found_error)
    return desired_capabilities.copy()
