import sys

from je_web_runner import webdriver_wrapper

try:
    webdriver_wrapper.set_driver("firefox")
    webdriver_wrapper.to_url("https://google.com")
    webdriver_wrapper.add_cookie({"name": "test_cookie_name", "value": "test_cookie_value"})
    print(webdriver_wrapper.get_cookies())
    webdriver_wrapper.delete_cookie("test_cookie_name")
    webdriver_wrapper.add_cookie({"name": "test_cookie_name_1", "value": "test_cookie_value_1"})
    webdriver_wrapper.add_cookie({"name": "test_cookie_name_2", "value": "test_cookie_value_2"})
    print(webdriver_wrapper.get_cookies())
    webdriver_wrapper.delete_all_cookies()
    cookies = webdriver_wrapper.get_cookies()
    print(cookies)
    assert len(cookies) == 0
    webdriver_wrapper.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)
