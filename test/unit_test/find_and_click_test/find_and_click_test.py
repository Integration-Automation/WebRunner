import sys

from je_web_runner import get_webdriver_manager
from je_web_runner import TestObject


driver_wrapper = get_webdriver_manager("firefox")
driver_wrapper.webdriver_wrapper.to_url("https://www.google.com")
google_input = TestObject("q", "name")
driver_wrapper.webdriver_wrapper.wait_implicitly(5)
element = driver_wrapper.webdriver_wrapper.find_element(google_input)
element.click()
element.send_keys("abc_test")
driver_wrapper.new_driver("firefox")
driver_wrapper.change_webdriver(0)
element = driver_wrapper.webdriver_wrapper.find_element(google_input)
element.send_keys("123")
driver_wrapper.change_webdriver(1)
driver_wrapper.webdriver_wrapper.to_url("https://www.google.com")
driver_wrapper.webdriver_wrapper.wait_implicitly(5)
element = driver_wrapper.webdriver_wrapper.find_element(google_input)
element.send_keys("123")
driver_wrapper.quit()
