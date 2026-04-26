import sys

from je_web_runner import get_webdriver_manager
from je_web_runner import webdriver_wrapper_instance

PYTHON_URL = "https://www.python.org"
FIREFOX = "firefox"


def _run() -> int:
    try:
        webdriver_manager = get_webdriver_manager(FIREFOX)
    except Exception as error:  # pylint: disable=broad-except
        print(f"multi_driver_test skipped: cannot start firefox ({error!r})", file=sys.stderr)
        return 0

    try:
        webdriver_wrapper_instance.to_url(PYTHON_URL)
        webdriver_manager.close_current_webdriver()
        for _ in range(5):
            webdriver_manager.new_driver(FIREFOX)
            webdriver_wrapper_instance.to_url(PYTHON_URL)
            webdriver_manager.close_current_webdriver()
        webdriver_manager.new_driver(FIREFOX)
        webdriver_wrapper_instance.to_url(PYTHON_URL)
        webdriver_manager.quit()
    except Exception as error:  # pylint: disable=broad-except
        print(repr(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_run())
