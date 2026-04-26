import sys

from je_web_runner import webdriver_wrapper_instance

try:
    webdriver_wrapper_instance.set_driver("firefox")
except Exception as error:  # pylint: disable=broad-except
    print(f"screenshot_test skipped: cannot start firefox ({error!r})", file=sys.stderr)
    sys.exit(0)

try:
    webdriver_wrapper_instance.get_screenshot_as_png()
    webdriver_wrapper_instance.get_screenshot_as_base64()
    webdriver_wrapper_instance.quit()
except Exception as error:  # pylint: disable=broad-except
    print(repr(error), file=sys.stderr)
    sys.exit(1)
