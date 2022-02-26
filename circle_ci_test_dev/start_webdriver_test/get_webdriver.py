from selenium_wrapper import get_webdriver

if __name__ == "__main__":
    driver_wrapper = get_webdriver(
        "chrome"
    )
    driver_wrapper.set_webdriver_options_capability({"test": "test"})
    driver_wrapper.open_browser("http://www.python.org")
    print(driver_wrapper.webdriver.title)
    driver_wrapper.quit()
