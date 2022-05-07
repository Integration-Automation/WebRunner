from selenium.webdriver import DesiredCapabilities

from je_eb_runner.utils.exception.exceptions import WebDriverException
from je_eb_runner.utils.exception.exception_tag import selenium_wrapper_web_driver_not_found_error


desired_capabilities_dict = {
    "firefox": DesiredCapabilities.FIREFOX,
    "chrome": DesiredCapabilities.CHROME,
    "edge": DesiredCapabilities.EDGE,
    "opera": DesiredCapabilities.OPERA,
    "safari": DesiredCapabilities.SAFARI,
}


def get_desired_capabilities_keys():
    return desired_capabilities_dict.keys()


def get_desired_capabilities(webdriver_name: str):
    desired_capabilities = desired_capabilities_dict.get(webdriver_name)
    if desired_capabilities is None:
        raise WebDriverException(selenium_wrapper_web_driver_not_found_error)
    return desired_capabilities.copy()


