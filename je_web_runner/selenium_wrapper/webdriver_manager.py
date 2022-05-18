from sys import stderr

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import WebDriverException

from je_web_runner.selenium_wrapper.web_element_wrapper import web_element_wrapper
from je_web_runner.utils.exception.exceptions import WebDriverIsNoneException

from je_web_runner.utils.exception.exception_tag import selenium_wrapper_web_driver_not_found_error


from je_web_runner.selenium_wrapper.webdriver_wrapper import webdriver_wrapper
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record


class WebdriverManager(object):

    def __init__(self, **kwargs):
        self._current_webdriver_list = list()
        self.webdriver_wrapper = webdriver_wrapper
        self.webdriver_element = web_element_wrapper
        self.current_webdriver: [WebDriver, None] = None

    def new_driver(self, webdriver_name: str, opera_path: str = None, **kwargs):
        self.current_webdriver = webdriver_wrapper.set_driver(webdriver_name, opera_path, **kwargs)
        self._current_webdriver_list.append(self.current_webdriver)

    def change_webdriver(self, index_of_webdriver: int):
        self.current_webdriver = self._current_webdriver_list[index_of_webdriver]
        self.webdriver_wrapper.current_webdriver = self.current_webdriver

    def close_current_webdriver(self):
        self._current_webdriver_list.remove(self.current_webdriver)
        self.current_webdriver.close()

    def close_choose_webdriver(self, webdriver_index):
        self.current_webdriver = self._current_webdriver_list[webdriver_index]
        self.current_webdriver.close()
        self._current_webdriver_list.remove(self._current_webdriver_list[webdriver_index])

    def quit(self):
        if self._current_webdriver_list is None:
            raise WebDriverIsNoneException(selenium_wrapper_web_driver_not_found_error)
        test_object_record.clean_record()
        try:
            for not_closed_webdriver in self._current_webdriver_list:
                not_closed_webdriver.close()
        except WebDriverException as error:
            print(repr(error), file=stderr)
        self.current_webdriver.quit()


def get_webdriver_manager(webdriver_name: str, opera_path: str = None, **kwargs):
    web_runner.new_driver(webdriver_name, opera_path)
    return web_runner


web_runner = WebdriverManager()
