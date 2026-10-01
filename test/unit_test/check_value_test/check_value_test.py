import sys
from sys import stderr

from je_web_runner import webdriver_wrapper_instance, TestObject, web_element_wrapper

try:
    webdriver_wrapper_instance.set_driver("firefox")
except Exception as error:  # pylint: disable=broad-except
    print(f"check_value_test skipped: cannot start firefox ({error!r})", file=stderr)
    sys.exit(0)

try:
    firefox_webdriver = webdriver_wrapper_instance.current_webdriver
    webdriver_wrapper_instance.to_url("https://www.python.org")
    webdriver_wrapper_instance.implicitly_wait(3)
    webdriver_wrapper_instance.check_current_webdriver(
        {
            "title": "Welcome to Python.org"
        }
    )
    try:
        webdriver_wrapper_instance.check_current_webdriver(
            {
                "title": "this should be raise exception"
            }
        )
    except Exception as error:  # pylint: disable=broad-except
        print(repr(error), file=stderr)

    google_input = TestObject("q", "name")
    webdriver_wrapper_instance.implicitly_wait(3)
    webdriver_wrapper_instance.find_element(google_input)
    # Only properties that reading does not change: location_once_scrolled_into_view scrolls the page, so it and
    # location can differ by a pixel between this read and the check's own read.
    web_element_wrapper.check_current_web_element(
        {
            "tag_name": web_element_wrapper.current_web_element.tag_name,
            "text": web_element_wrapper.current_web_element.text,
            "size": web_element_wrapper.current_web_element.size,
            "parent": web_element_wrapper.current_web_element.parent,
            "id": web_element_wrapper.current_web_element.id,
        }
    )

    webdriver_wrapper_instance.quit()
except Exception as error:  # pylint: disable=broad-except
    print(repr(error), file=stderr)
    sys.exit(1)
