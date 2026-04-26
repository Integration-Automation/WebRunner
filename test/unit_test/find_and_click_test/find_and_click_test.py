import sys

from je_web_runner import TestObject
from je_web_runner import get_webdriver_manager
from je_web_runner import web_element_wrapper
from je_web_runner import webdriver_wrapper_instance

try:
    driver_wrapper = get_webdriver_manager("firefox")
except Exception as error:  # pylint: disable=broad-except
    print(f"find_and_click_test skipped: cannot start firefox ({error!r})", file=sys.stderr)
    sys.exit(0)

try:
    driver_wrapper.webdriver_wrapper.to_url("https://www.google.com")
    google_input = TestObject("q", "name")
    driver_wrapper.webdriver_wrapper.implicitly_wait(2)
    webdriver_wrapper_instance.find_element(google_input)
    web_element_wrapper.click_element()
    web_element_wrapper.input_to_element("abc_test")
    driver_wrapper.new_driver("firefox")
    driver_wrapper.change_webdriver(0)
    webdriver_wrapper_instance.find_element(google_input)
    web_element_wrapper.input_to_element("123")
    driver_wrapper.change_webdriver(1)
    webdriver_wrapper_instance.to_url("https://www.google.com")
    webdriver_wrapper_instance.implicitly_wait(5)
    webdriver_wrapper_instance.find_element(google_input)
    web_element_wrapper.input_to_element("123")
    driver_wrapper.quit()
except Exception as error:  # pylint: disable=broad-except
    print(repr(error), file=sys.stderr)
    sys.exit(1)
