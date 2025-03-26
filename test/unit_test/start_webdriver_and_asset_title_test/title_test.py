import sys

from je_web_runner import webdriver_wrapper_instance

try:
    web_manager = webdriver_wrapper_instance.set_driver("firefox")

    firefox_webdriver = webdriver_wrapper_instance.current_webdriver

    firefox_webdriver.get("http://www.python.org")

    firefox_webdriver.implicitly_wait(1)

    assert firefox_webdriver.title == "Welcome to Python.org"

    web_manager.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    firefox_webdriver = webdriver_wrapper_instance.current_webdriver.quit()
    sys.exit(1)

