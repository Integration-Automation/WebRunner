import sys

from je_web_runner import webdriver_wrapper_instance

try:
    webdriver_wrapper_instance.set_driver("firefox")
    webdriver_wrapper_instance.minimize_window()
    webdriver_wrapper_instance.maximize_window()
    webdriver_wrapper_instance.fullscreen_window()
    webdriver_wrapper_instance.set_window_size(500, 500)
    webdriver_wrapper_instance.set_window_position(100, 100)
    webdriver_wrapper_instance.get_window_position()
    webdriver_wrapper_instance.get_window_rect()
    webdriver_wrapper_instance.set_window_rect(500, 500, 500, 500)
    webdriver_wrapper_instance.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)
