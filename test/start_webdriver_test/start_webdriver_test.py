import time
from selenium_wrapper import set_web_driver
from selenium_wrapper import close_driver


if __name__ == "__main__":
    driver = set_web_driver(
        "firefox",
        r"D:\WorkSpaces\Program WorkSpace\Python\Project\SeleniumWrapper\test\geckodriver.exe")
    time.sleep(3)
    close_driver(driver)
