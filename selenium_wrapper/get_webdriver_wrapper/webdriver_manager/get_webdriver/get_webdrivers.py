from selenium_wrapper.selenium_webdrive_wrapper.webdriver_wrapper import WebdriverWrapper


def get_webdriver(web_driver_name: str = "chrome", opera_path: str = None, **kwargs):
    return WebdriverWrapper(web_driver_name, opera_path, **kwargs)
