from je_web_runner import get_webdriver_manager
from je_web_runner import TestObject

driver_wrapper = get_webdriver_manager("firefox")
driver_wrapper.open_browser("https://www.google.com.tw")
google_input = TestObject("q", "name")
driver_wrapper.webdriver.implicitly_wait(5)
driver_wrapper.find_element(google_input).click()
driver_wrapper.find_element(google_input).send_keys("abc_test")
driver_wrapper.set_driver("firefox")
print(driver_wrapper.current_webdriver_list)
driver_wrapper.webdriver = driver_wrapper.current_webdriver_list[0]
driver_wrapper.find_element(google_input).send_keys(" 123")
driver_wrapper.quit()
