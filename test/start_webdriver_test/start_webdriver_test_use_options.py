import time
from selenium_wrapper import get_webdriver_use_options
from selenium_wrapper import close_driver


if __name__ == "__main__":
    driver = get_webdriver_use_options(
        "firefox",
        r"C:\Program_SSD_Workspace\Python\Project\SeleniumWrapper_JE\test\geckodriver.exe"
    )
    driver.get("http://www.python.org")
    print(driver.title)
    time.sleep(3)
    close_driver(driver)
