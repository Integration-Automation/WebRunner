from web_runner import get_webdriver
from web_runner import set_webdriver_options_argument

driver_wrapper = get_webdriver("chrome", options=set_webdriver_options_argument("chrome", ["--disable-extensions"]))
driver_wrapper.set_driver("firefox", options=set_webdriver_options_argument("firefox", ["--headless"]))
