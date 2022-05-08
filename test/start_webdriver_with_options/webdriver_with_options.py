import sys

from je_web_runner import get_webdriver_manager
from je_web_runner import set_webdriver_options_argument

try:
    driver_wrapper = get_webdriver_manager("firefox", options=set_webdriver_options_argument("firefox", ["--disable-extensions"]))
    driver_wrapper.set_driver("firefox", options=set_webdriver_options_argument("firefox", ["--headless"]))
    driver_wrapper.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)