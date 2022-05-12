import sys

from je_web_runner import get_webdriver_manager
from je_web_runner import webdriver_wrapper

try:
    if __name__ == "__main__":
        webdriver_manager = get_webdriver_manager(
            "firefox"
        )
        webdriver_wrapper.set_webdriver_options_capability({"test": "test"})
        webdriver_wrapper.to_url("http://www.python.org")
        print(webdriver_manager.webdriver_wrapper.current_webdriver.title)
        webdriver_manager.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)
