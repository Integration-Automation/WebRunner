import sys

from je_web_runner import get_webdriver_manager
from je_web_runner import webdriver_wrapper

try:
    if __name__ == "__main__":
        webdriver_manager = get_webdriver_manager("firefox")
        webdriver_wrapper.to_url("http://www.python.org")
        webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver("firefox")
        webdriver_wrapper.to_url("http://www.python.org")
        webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver("firefox")
        webdriver_wrapper.to_url("http://www.python.org")
        webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver("firefox")
        webdriver_wrapper.to_url("http://www.python.org")
        webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver("firefox")
        webdriver_wrapper.to_url("http://www.python.org")
        webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver("firefox")
        webdriver_wrapper.to_url("http://www.python.org")
        webdriver_manager.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)
