from sys import stderr

from je_web_runner import TestObject
from je_web_runner import webdriver_wrapper

try:
    webdriver_wrapper.set_driver("firefox")
    firefox_webdriver = webdriver_wrapper.current_webdriver
    webdriver_wrapper.to_url("http://www.python.org")
    google_input = TestObject("q", "name")
    webdriver_wrapper.implicitly_wait(3)
    webdriver_wrapper.find_element(google_input)
    webdriver_wrapper.switch("active_element")
    webdriver_wrapper.switch("parent_frame")
    webdriver_wrapper.switch("default_content")
    webdriver_wrapper.quit()
except Exception as error:
    print(repr(error), file=stderr)
