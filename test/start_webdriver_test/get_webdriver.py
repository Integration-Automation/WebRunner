import time
from selenium_wrapper import get_webdriver
from selenium_wrapper import close_driver


if __name__ == "__main__":
    driver = get_webdriver(
        "firefox",
    )
    driver.get("http://www.python.org")
    print(driver.title)
    time.sleep(1)
    close_driver(driver)
