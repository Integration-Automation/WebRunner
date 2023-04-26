import sys

from je_web_runner import webdriver_wrapper

try:
    webdriver_wrapper.set_driver("firefox")
    webdriver_wrapper.minimize_window()
    webdriver_wrapper.maximize_window()
    webdriver_wrapper.full_screen_window()
    webdriver_wrapper.set_window_size(500, 500)
    webdriver_wrapper.set_window_position(100, 100)
    webdriver_wrapper.get_window_position()
    webdriver_wrapper.get_window_rect()
    webdriver_wrapper.set_window_rect(500, 500, 500, 500)
    webdriver_wrapper.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)
