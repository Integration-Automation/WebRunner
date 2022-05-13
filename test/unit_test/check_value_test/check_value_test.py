from sys import stderr

from je_web_runner import webdriver_wrapper

webdriver_wrapper.set_driver("firefox")
firefox_webdriver = webdriver_wrapper.current_webdriver
webdriver_wrapper.to_url("http://www.python.org")
webdriver_wrapper.wait_implicitly(3)
webdriver_wrapper.check_current_webdriver(
    {
        "title": "Welcome to Python.org"
     }
)
try:
    webdriver_wrapper.check_current_webdriver(
        {
            "title": "this should be raise exception"
        }
    )
except Exception as error:
    print(repr(error), file=stderr)
webdriver_wrapper.quit()
