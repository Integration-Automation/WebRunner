import sys

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.edge.service import Service
from selenium.webdriver.ie.service import Service
from selenium.webdriver.safari.service import Service
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

webdriver_service_dict = {
    "chrome": webdriver.chrome.service.Service,
    "chromium": webdriver.chrome.service.Service,
    "firefox": webdriver.firefox.service.Service,
    "edge": webdriver.edge.service.Service,
    "ie": webdriver.ie.service.Service,
    "safari": webdriver.safari.service.Service,
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


def get_webdriver(web_driver_name: str, opera_path: str = None, **kwargs):
    web_driver_name = str(web_driver_name).lower()
    webdriver_value = webdriver_dict.get(web_driver_name)
    webdriver_install_manager = webdriver_manager_dict.get(web_driver_name)
    if web_driver_name in ["opera"]:
        opera_options = webdriver.ChromeOptions()
        opera_options.add_argument('allow-elevated-browser')
        opera_options.binary_location = opera_path
        return webdriver_value(
            executable_path=webdriver_manager_dict.get(web_driver_name)().install(), options=opera_options, **kwargs
        )
    else:
        webdriver_service = webdriver_service_dict.get(web_driver_name)(
            webdriver_install_manager().install(),
            **kwargs
        )
        return webdriver_value(service=webdriver_service, **kwargs)
