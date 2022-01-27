from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.opera import OperaDriverManager
from webdriver_manager.microsoft import IEDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.utils import ChromeType

webdriver_manager_dict = {
    "chrome": ChromeDriverManager,
    "chromium": ChromeDriverManager(chrome_type=ChromeType.CHROMIUM),
    "firefox": GeckoDriverManager,
    "opera": OperaDriverManager,
    "edge": EdgeChromiumDriverManager,
    "ie": IEDriverManager,
}

webdriver_dict = {
    "chrome": webdriver.Chrome,
    "chromium": webdriver.Chrome,
    "firefox": webdriver.Firefox,
    "opera": webdriver.Opera,
    "edge": webdriver.Edge,
    "ie": webdriver.Ie,
    "safari": webdriver.Safari,
}


def get_webdriver(web_driver_name: str, **kwargs):
    web_driver_name = str(web_driver_name).lower()
    webdriver_value = webdriver_dict.get(web_driver_name)
    webdriver_install_manager = webdriver_manager_dict.get(web_driver_name)
    if web_driver_name in ["edge", "ie"]:
        return webdriver_value(webdriver_install_manager().install(), **kwargs)
    else:
        return webdriver_value(executable_path=webdriver_install_manager().install(), **kwargs)
