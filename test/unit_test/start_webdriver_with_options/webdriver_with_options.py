import sys

from je_web_runner import get_webdriver_manager
from je_web_runner import set_webdriver_options_argument

try:
    webdriver_manager = get_webdriver_manager(
        "firefox",
        options=set_webdriver_options_argument("firefox", ["--disable-extensions"]),
    )
except Exception as error:  # pylint: disable=broad-except
    print(f"webdriver_with_options skipped: cannot start firefox ({error!r})", file=sys.stderr)
    sys.exit(0)

try:
    webdriver_manager.new_driver(
        "firefox",
        options=set_webdriver_options_argument("firefox", ["--headless"]),
    )
    webdriver_manager.quit()
except Exception as error:  # pylint: disable=broad-except
    print(repr(error), file=sys.stderr)
    sys.exit(1)
