import sys

from je_web_runner import get_webdriver_manager
from je_web_runner import webdriver_wrapper_instance

PYTHON_URL = "https://www.python.org"
FIREFOX = "firefox"

try:
    if __name__ == "__main__":
        webdriver_manager = get_webdriver_manager(FIREFOX)
        webdriver_wrapper_instance.to_url(PYTHON_URL)
        webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver(FIREFOX)
        webdriver_wrapper_instance.to_url(PYTHON_URL)
        webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver(FIREFOX)
        webdriver_wrapper_instance.to_url(PYTHON_URL)
        webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver(FIREFOX)
        webdriver_wrapper_instance.to_url(PYTHON_URL)
        webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver(FIREFOX)
        webdriver_wrapper_instance.to_url(PYTHON_URL)
        webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver(FIREFOX)
        webdriver_wrapper_instance.to_url(PYTHON_URL)
        webdriver_manager.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)
