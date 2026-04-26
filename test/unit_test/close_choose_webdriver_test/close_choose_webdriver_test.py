import sys

from je_web_runner import get_webdriver_manager

try:
    webdriver_manager = get_webdriver_manager("firefox")
except Exception as error:  # pylint: disable=broad-except
    print(f"close_choose_webdriver_test skipped: cannot start firefox ({error!r})", file=sys.stderr)
    sys.exit(0)

try:
    webdriver_manager.new_driver("firefox")
    webdriver_manager.close_choose_webdriver(1)
    webdriver_manager.close_choose_webdriver(0)
    webdriver_manager.quit()
except Exception as error:  # pylint: disable=broad-except
    print(repr(error), file=sys.stderr)
    sys.exit(1)
