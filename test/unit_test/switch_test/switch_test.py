from sys import stderr

from je_web_runner import TestObject
from je_web_runner import webdriver_wrapper_instance

try:
    webdriver_wrapper_instance.set_driver("firefox")
    firefox_webdriver = webdriver_wrapper_instance.current_webdriver
    webdriver_wrapper_instance.to_url("https://www.google.com")
    google_input = TestObject("q", "name")
    webdriver_wrapper_instance.implicitly_wait(3)
    webdriver_wrapper_instance.find_element(google_input)
    webdriver_wrapper_instance.switch("active_element")
    webdriver_wrapper_instance.switch("parent_frame")
    webdriver_wrapper_instance.switch("default_content")
    webdriver_wrapper_instance.quit()
except Exception as error:
    print(repr(error), file=stderr)
