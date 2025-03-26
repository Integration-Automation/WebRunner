from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance
from je_web_runner.utils.exception.exception_tags import selenium_wrapper_web_driver_not_found_error
from je_web_runner.utils.exception.exceptions import WebRunnerWebDriverIsNoneException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class WebdriverManager(object):

    def __init__(self, **kwargs):
        self._current_webdriver_list = list()
        self.webdriver_wrapper = webdriver_wrapper_instance
        self.webdriver_element = web_element_wrapper
        self.current_webdriver: [WebDriver, None] = None

    def new_driver(self, webdriver_name: str, **kwargs) -> None:
        """
        use to create new webdriver instance
        :param webdriver_name: which webdriver we want to use [chrome, chromium, firefox, edge, ie]
        :param kwargs: webdriver download manager param
        :return: None
        """
        web_runner_logger.info(f"WebdriverManager new_driver, webdriver_name: {webdriver_name}, params: {kwargs}")
        param = locals()
        try:
            self.current_webdriver = webdriver_wrapper_instance.set_driver(webdriver_name, **kwargs)
            self._current_webdriver_list.append(self.current_webdriver)
            record_action_to_list("web runner manager new_driver", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebdriverManager new_driver, webdriver_name: {webdriver_name}, params: {kwargs}, failed: {repr(error)}"
            )
            record_action_to_list("web runner manager new_driver", param, error)
            self.quit()

    def change_webdriver(self, index_of_webdriver: int) -> None:
        """
        change to target webdriver
        :param index_of_webdriver: change current webdriver to choose index webdriver
        :return: None
        """
        web_runner_logger.info(f"WebdriverManager change_webdriver, index_of_webdriver: {index_of_webdriver}")
        param = locals()
        try:
            self.current_webdriver = self._current_webdriver_list[index_of_webdriver]
            self.webdriver_wrapper.current_webdriver = self.current_webdriver
            record_action_to_list("web runner manager change_webdriver", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebdriverManager change_webdriver, index_of_webdriver: {index_of_webdriver}, failed: {repr(error)}")
            record_action_to_list("web runner manager change_webdriver", param, error)

    def close_current_webdriver(self) -> None:
        """
        close current webdriver
        :return: None
        """
        web_runner_logger.info(f"WebdriverManager close_current_webdriver")
        try:
            self._current_webdriver_list.remove(self.current_webdriver)
            self.current_webdriver.close()
            record_action_to_list("web runner manager close_current_webdriver", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebdriverManager close_current_webdriver, failed: {repr(error)}")
            record_action_to_list("web runner manager close_current_webdriver", None, error)

    def close_choose_webdriver(self, webdriver_index: int) -> None:
        """
        close choose webdriver
        :param webdriver_index: close choose webdriver on current webdriver list
        :return: None
        """
        web_runner_logger.info(f"WebdriverManager close_choose_webdriver")
        param = locals()
        try:
            self.current_webdriver = self._current_webdriver_list[webdriver_index]
            self.current_webdriver.close()
            self._current_webdriver_list.remove(self._current_webdriver_list[webdriver_index])
            record_action_to_list("web runner manager close_choose_webdriver", param, None)
        except Exception as error:
            web_runner_logger.info(f"WebdriverManager close_choose_webdriver, failed: {repr(error)}")
            record_action_to_list("web runner manager close_choose_webdriver", param, error)

    def quit(self) -> None:
        """
        close and quit all webdriver instance
        :return: None
        """
        web_runner_logger.info(f"WebdriverManager quit")
        try:
            if self._current_webdriver_list is None:
                raise WebRunnerWebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
            test_object_record.clean_record()
            for webdriver in self._current_webdriver_list:
                webdriver.quit()
            self._current_webdriver_list = list()
            record_action_to_list("web runner manager quit", None, None)
        except Exception as error:
            web_runner_logger.info(f"WebdriverManager quit, failed: {repr(error)}")
            record_action_to_list("web runner manager quit", None, error)
            raise WebDriverException


def get_webdriver_manager(webdriver_name: str, **kwargs) -> WebdriverManager:
    """
    use to get webdriver instance
    :param webdriver_name: which webdriver we want to use [chrome, chromium, firefox, edge, ie]
    :param kwargs: webdriver download manager param
    :return: Webdriver manager instance
    """
    web_runner_logger.info(f"get_webdriver_manager, webdriver_name: {webdriver_name}, params: {kwargs}")
    web_runner.new_driver(webdriver_name, **kwargs)
    return web_runner


web_runner = WebdriverManager()
