import sys

from je_web_runner import webdriver_wrapper_instance

try:
    webdriver_wrapper_instance.set_driver("firefox")
    webdriver_wrapper_instance.to_url("https://google.com")
    webdriver_wrapper_instance.add_cookie({"name": "test_cookie_name", "value": "test_cookie_value"})
    print(webdriver_wrapper_instance.get_cookies())
    webdriver_wrapper_instance.delete_cookie("test_cookie_name")
    webdriver_wrapper_instance.add_cookie({"name": "test_cookie_name_1", "value": "test_cookie_value_1"})
    webdriver_wrapper_instance.add_cookie({"name": "test_cookie_name_2", "value": "test_cookie_value_2"})
    print(webdriver_wrapper_instance.get_cookies())
    webdriver_wrapper_instance.delete_all_cookies()
    cookies = webdriver_wrapper_instance.get_cookies()
    print(cookies)
    webdriver_wrapper_instance.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)
