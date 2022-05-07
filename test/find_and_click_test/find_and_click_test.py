from web_runner import get_webdriver
from web_runner import TestObject

driver_wrapper = get_webdriver("chrome")
driver_wrapper.open_browser("https://www.google.com.tw")
google_input = TestObject("q", "name")
driver_wrapper.webdriver.implicitly_wait(5)
driver_wrapper.find_element(google_input).click()
driver_wrapper.find_element(google_input).send_keys("abc_test")
driver_wrapper.quit()
