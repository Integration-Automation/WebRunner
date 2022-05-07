from je_web_runner import get_webdriver
from je_web_runner import set_webdriver_options_argument

driver_wrapper = get_webdriver("firefox", options=set_webdriver_options_argument("firefox", ["--disable-extensions"]))
driver_wrapper.set_driver("firefox", options=set_webdriver_options_argument("firefox", ["--headless"]))
