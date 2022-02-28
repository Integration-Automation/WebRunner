from selenium_wrapper import get_webdriver
from selenium_wrapper import set_webdriver_options_argument

driver_wrapper = get_webdriver("edge", options=set_webdriver_options_argument("edge", ["--disable-extensions"]))
driver_wrapper.set_driver("edge", options=set_webdriver_options_argument("edge", ["--headless"]))
