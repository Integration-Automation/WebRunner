import sys

from je_web_runner import webdriver_wrapper_instance

try:
    web_manager = webdriver_wrapper_instance.set_driver("firefox")
except Exception as error:  # pylint: disable=broad-except
    print(f"title_test skipped: cannot start firefox ({error!r})", file=sys.stderr)
    sys.exit(0)

try:
    firefox_webdriver = webdriver_wrapper_instance.current_webdriver
    firefox_webdriver.get("https://www.python.org")
    firefox_webdriver.implicitly_wait(1)
    if firefox_webdriver.title != "Welcome to Python.org":
        raise AssertionError(f"Unexpected title: {firefox_webdriver.title!r}")
    web_manager.quit()
except Exception as error:  # pylint: disable=broad-except
    print(repr(error), file=sys.stderr)
    try:
        webdriver_wrapper_instance.current_webdriver.quit()
    except Exception as quit_error:  # pylint: disable=broad-except  # nosec B110
        print(f"quit during cleanup failed: {quit_error!r}", file=sys.stderr)
    sys.exit(1)
