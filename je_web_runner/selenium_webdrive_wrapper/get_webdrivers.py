from je_web_runner.selenium_webdrive_wrapper.webdriver_wrapper import web_runner


def get_webdriver_manager(webdriver_name: str = "chrome", opera_path: str = None, **kwargs):
    web_runner.set_driver(webdriver_name, opera_path, **kwargs)
    return web_runner
