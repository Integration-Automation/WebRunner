import time
from selenium_wrapper import get_webdriver
from selenium_wrapper import close_driver


if __name__ == "__main__":
    driver = get_webdriver(
        "opera",
        r"C:\Users\JE-Chen\.wdm\drivers\operadriver\win64\v.97.0.4692.71\operadriver_win64/"
    )
    driver.get("http://www.python.org")
    print(driver.title)
    time.sleep(1)
    close_driver(driver)
