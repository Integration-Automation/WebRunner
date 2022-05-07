from web_runner.selenium_webdrive_wrapper.webdriver_wrapper import WebdriverWrapper


def get_webdriver(webdriver_name: str = "chrome", opera_path: str = None, **kwargs):
    return WebdriverWrapper(webdriver_name, opera_path, **kwargs)
