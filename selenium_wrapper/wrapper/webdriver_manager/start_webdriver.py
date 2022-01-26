from selenium import webdriver
from selenium.webdriver.safari import service
from selenium.webdriver.firefox import service
from selenium.webdriver.chrome import service
from selenium.webdriver.edge import service
from selenium.webdriver.ie import service
from selenium.webdriver.webkitgtk import service
from selenium.webdriver.chrome import options
from selenium.webdriver.firefox import options
from selenium.webdriver.edge import options
from selenium.webdriver.ie import options
from selenium.webdriver.webkitgtk import options
from selenium.webdriver.opera import options

webdriver_service_dict = {
    "safari": [webdriver.Safari, webdriver.safari.service.Service],
    "firefox": [webdriver.Firefox, webdriver.firefox.service.Service],
    "chrome": [webdriver.Chrome, webdriver.chrome.service.Service],
    "edge": [webdriver.Edge, webdriver.edge.service.Service],
    "ie": [webdriver.Ie, webdriver.ie.service.Service],
    "opera": [webdriver.Opera],
    "webkitgtk": [webdriver.WebKitGTK, webdriver.webkitgtk.service.Service],
    "remote": [webdriver.Remote],
}

webdriver_options_dict = {
    "firefox": [webdriver.Firefox, webdriver.firefox.options.Options],
    "chrome": [webdriver.Chrome, webdriver.chrome.options.Options],
    "edge": [webdriver.Edge, webdriver.edge.options.Options],
    "ie": [webdriver.Ie, webdriver.ie.options.Options],
    "opera": [webdriver.Opera, webdriver.opera.options.Options],
    "webkitgtk": [webdriver.WebKitGTK, webdriver.webkitgtk.options.Options],
}


def get_webdriver_use_options(web_driver: str, web_driver_path=None, **kwargs):
    web_driver = str(web_driver).lower()
    webdriver_options_info = webdriver_options_dict.get(web_driver)
    webdriver_service_info = webdriver_service_dict.get(web_driver)
    web_driver = webdriver_options_info[0](
        options=webdriver_options_info[1](**kwargs),
        service=webdriver_service_info[1](web_driver_path)
    )
    return web_driver


def get_webdriver_use_service(web_driver: str, web_driver_path=None, **kwargs):
    web_driver = str(web_driver).lower()
    webdriver_service_info = webdriver_service_dict.get(web_driver)
    if web_driver not in ["opera", "remote"]:
        web_service = webdriver_service_info[1](web_driver_path)
        web_driver = webdriver_service_info[0](service=web_service, **kwargs)
    else:
        web_driver = webdriver_service_info[0](executable_path=web_driver_path, **kwargs)
    return web_driver


def get_webdriver(web_driver: str, **kwargs):
    web_driver = str(web_driver).lower()
    return webdriver_options_dict.get(web_driver)[0](**kwargs)
