from selenium_wrapper import get_webdriver

if __name__ == "__main__":
    driver_wrapper = get_webdriver("edge")
    driver = driver_wrapper.webdriver
    driver_wrapper.open_browser("http://www.python.org")
    print(driver.title)
    driver_wrapper.set_driver("edge")
    driver_wrapper.open_browser("http://www.python.org")
    print(driver.title)
    driver_wrapper.set_driver("edge")
    driver_wrapper.open_browser("http://www.python.org")
    print(driver.title)
    driver_wrapper.set_driver("edge")
    driver_wrapper.open_browser("http://www.python.org")
    print(driver.title)
    driver_wrapper.set_driver("edge")
    driver_wrapper.open_browser("http://www.python.org")
    print(driver.title)
    driver_wrapper.set_driver("edge")
    driver_wrapper.open_browser("http://www.python.org")
    print(driver.title)
    print(driver_wrapper.current_webdriver_list)
    driver_wrapper.quit()
