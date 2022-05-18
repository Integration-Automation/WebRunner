import sys

from je_web_runner import webdriver_wrapper

try:
    webdriver_wrapper.set_driver("firefox")
    webdriver_wrapper.get_screenshot_as_png()
    webdriver_wrapper.get_screenshot_as_base64()
    webdriver_wrapper.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)