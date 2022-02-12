from selenium_wrapper import get_webdriver

firefox_webdriver = get_webdriver("firefox")

firefox_webdriver.get("http://www.python.org")

assert firefox_webdriver.title == "Welcome to Python.org"

firefox_webdriver.close()
