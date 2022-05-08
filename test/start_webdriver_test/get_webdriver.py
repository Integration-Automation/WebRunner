import sys

from je_web_runner import get_webdriver_manager

try:
    if __name__ == "__main__":
        driver_wrapper = get_webdriver_manager(
            "firefox"
        )
        driver_wrapper.set_webdriver_options_capability({"test": "test"})
        driver_wrapper.open_browser("http://www.python.org")
        print(driver_wrapper.webdriver.title)
        driver_wrapper.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)