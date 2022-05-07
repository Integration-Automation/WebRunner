from web_runner import get_webdriver

if __name__ == "__main__":
    driver_wrapper = get_webdriver("firefox")
    driver = driver_wrapper.webdriver
    driver.get("http://www.python.org")
    print(driver.title)
    driver_wrapper.close()
