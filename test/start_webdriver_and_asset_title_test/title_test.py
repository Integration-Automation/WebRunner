import sys

from je_web_runner import get_webdriver_manager

try:
    firefox_webdriver_wrapper = get_webdriver_manager("firefox")

    firefox_webdriver = firefox_webdriver_wrapper.webdriver

    firefox_webdriver.get("http://www.python.org")

    firefox_webdriver.implicitly_wait(1)

    assert firefox_webdriver.title == "Welcome to Python.org"

    firefox_webdriver_wrapper.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)