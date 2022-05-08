from je_web_runner import get_webdriver_manager

if __name__ == "__main__":
    driver_wrapper = get_webdriver_manager(
        "firefox"
    )
    driver_wrapper.set_webdriver_options_capability({"test": "test"})
    driver_wrapper.open_browser("http://www.python.org")
    print(driver_wrapper.webdriver.title)
    driver_wrapper.quit()
