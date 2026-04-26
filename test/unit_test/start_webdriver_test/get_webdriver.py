import sys

from je_web_runner import get_webdriver_manager
from je_web_runner import webdriver_wrapper_instance


def _run() -> int:
    try:
        webdriver_manager = get_webdriver_manager("firefox")
    except Exception as error:  # pylint: disable=broad-except
        print(f"get_webdriver skipped: cannot start firefox ({error!r})", file=sys.stderr)
        return 0

    try:
        webdriver_wrapper_instance.set_webdriver_options_capability({"test": "test"})
        webdriver_wrapper_instance.to_url("https://www.python.org")
        print(webdriver_manager.webdriver_wrapper.current_webdriver.title)
        webdriver_manager.quit()
    except Exception as error:  # pylint: disable=broad-except
        print(repr(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_run())
