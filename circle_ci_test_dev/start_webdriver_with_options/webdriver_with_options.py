from selenium_wrapper import get_webdriver
from selenium_wrapper import set_webdriver_options_argument

driver_wrapper = get_webdriver("chrome", options=set_webdriver_options_argument("chrome", ["--disable-extensions"]))
driver_wrapper.set_driver("firefox", options=set_webdriver_options_argument("firefox", ["--headless"]))
