from sys import stderr
from typing import Union

from selenium import webdriver
from selenium.webdriver.chrome import options
from selenium.webdriver.edge import options
from selenium.webdriver.firefox import options
from selenium.webdriver.ie import options

from je_web_runner.utils.exception.exception_tags import selenium_wrapper_set_argument_error
from je_web_runner.utils.exception.exception_tags import selenium_wrapper_set_options_error
from je_web_runner.utils.exception.exception_tags import selenium_wrapper_web_driver_not_found_error
from je_web_runner.utils.exception.exceptions import WebRunnerArgumentWrongTypeException
from je_web_runner.utils.exception.exceptions import WebRunnerOptionsWrongTypeException
from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverNotFoundException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import record_action_to_list

selenium_options_dict = {
    "chrome": webdriver.chrome.options.Options,
    "chromium": webdriver.chrome.options.Options,
    "firefox": webdriver.firefox.options.Options,
    "edge": webdriver.edge.options.Options,
    "ie": webdriver.ie.options.Options,
}


def set_webdriver_options_argument(webdriver_name: str, argument_iterable: [list, set]) -> \
        Union[
            webdriver.chrome.options.Options, webdriver.chrome.options.Options,
            webdriver.edge.options.Options, webdriver.ie.options.Options
        ]:
    """
    :param webdriver_name: use name to open webdriver manager and download webdriver
    :param argument_iterable: start webdriver argument
    :return: webdriver
    """
    web_runner_logger.info(
        f"set_webdriver_options_argument, webdriver_name: {webdriver_name}, argument_iterable: {argument_iterable}"
    )
    param = locals()
    try:
        webdriver_options = selenium_options_dict.get(webdriver_name)()
        for index, value in enumerate(argument_iterable):
            if isinstance(value, str) is False:
                raise WebRunnerArgumentWrongTypeException(selenium_wrapper_set_argument_error)
            webdriver_options.add_argument(value)
        record_action_to_list("webdriver with options set_webdriver_options_argument", param, None)
        return webdriver_options
    except Exception as error:
        web_runner_logger.error(
            f"set_webdriver_options_argument, webdriver_name: {webdriver_name}, "
            f"argument_iterable: {argument_iterable}, failed: {repr(error)}"
        )
        record_action_to_list("webdriver with options set_webdriver_options_argument", param, error)


def set_webdriver_options_capability_wrapper(webdriver_name: str, key_and_vale_dict: dict) -> \
        Union[
            webdriver.chrome.options.Options, webdriver.chrome.options.Options,
            webdriver.edge.options.Options, webdriver.ie.options.Options
        ]:
    """
    :param webdriver_name:  use name to open webdriver manager and download webdriver
    :param key_and_vale_dict: set webdriver options capability
    :return: webdriver
    """
    web_runner_logger.info(
        f"set_webdriver_options_capability_wrapper, webdriver_name: {webdriver_name}, "
        f"key_and_vale_dict: {key_and_vale_dict}"
    )
    param = locals()
    try:
        webdriver_options = selenium_options_dict.get(webdriver_name)()
        if webdriver_options is None:
            raise WebRunnerWebDriverNotFoundException(selenium_wrapper_web_driver_not_found_error)
        if isinstance(key_and_vale_dict, dict) is False:
            raise WebRunnerOptionsWrongTypeException(selenium_wrapper_set_options_error)
        for key, value in key_and_vale_dict.items():
            webdriver_options.set_capability(key, value)
        record_action_to_list("webdriver with options set_webdriver_options_capability_wrapper", param, None)
        return webdriver_options
    except Exception as error:
        web_runner_logger.error(
            f"set_webdriver_options_capability_wrapper, webdriver_name: {webdriver_name}, "
            f"key_and_vale_dict: {key_and_vale_dict}, failed: {repr(error)}"
        )
        record_action_to_list("webdriver with options set_webdriver_options_capability_wrapper", param, error)
