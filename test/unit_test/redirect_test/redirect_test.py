import sys

from je_web_runner import webdriver_wrapper_instance

try:
    webdriver_wrapper_instance.set_driver("firefox")
except Exception as error:  # pylint: disable=broad-except
    # CI sandboxes without Firefox + geckodriver should not block the run.
    print(f"redirect_test skipped: cannot start firefox ({error!r})", file=sys.stderr)
    sys.exit(0)

try:
    webdriver_wrapper_instance.implicitly_wait(5)
    webdriver_wrapper_instance.to_url("https://music.youtube.com/")
    webdriver_wrapper_instance.back()
    webdriver_wrapper_instance.refresh()
    webdriver_wrapper_instance.forward()
    webdriver_wrapper_instance.quit()
except Exception as error:  # pylint: disable=broad-except
    print(repr(error), file=sys.stderr)
    sys.exit(1)
