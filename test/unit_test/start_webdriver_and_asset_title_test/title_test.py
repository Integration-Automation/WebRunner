import sys

from je_web_runner import get_webdriver_manager

try:
    web_manager = get_webdriver_manager("firefox")

    firefox_webdriver = web_manager.webdriver_wrapper.current_webdriver

    firefox_webdriver.get("http://www.python.org")

    firefox_webdriver.implicitly_wait(1)

    assert firefox_webdriver.title == "Welcome to Python.org"

    web_manager.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)