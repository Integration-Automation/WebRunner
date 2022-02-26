from selenium_wrapper import get_webdriver
from selenium_wrapper import TestObject

driver_wrapper = get_webdriver("edge")
driver_wrapper.open_browser("https://www.google.com.tw")
google_input = TestObject("q", "name")
driver_wrapper.webdriver.implicitly_wait(5)
driver_wrapper.find_element(google_input).click()
driver_wrapper.find_element(google_input).send_keys("abc_test")
driver_wrapper.quit()
