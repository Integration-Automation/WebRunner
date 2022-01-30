import time
from selenium_wrapper import get_webdriver
from selenium_wrapper import close_driver
from selenium_wrapper import set_webdriver_options


if __name__ == "__main__":
    driver = get_webdriver(
        "chrome",
        set_webdriver_options("chrome", key_and_vale_dict={"headless": True})
    )
    driver.get("http://www.python.org")
    print(driver.title)
    time.sleep(1)
    close_driver(driver)
