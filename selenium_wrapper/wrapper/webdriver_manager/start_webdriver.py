from selenium import webdriver
from selenium.webdriver.safari import service

webdriver_dict = {
    "safari": [webdriver.Safari, webdriver.safari.service.Service],
    "firefox": [webdriver.Firefox, webdriver.firefox.service.Service],
    "chrome": [webdriver.Chrome, webdriver.chrome.service.Service],
    "edge": [webdriver.Edge, webdriver.edge.service.Service],
    "ie": [webdriver.Ie, webdriver.ie.service.Service],
    "opera": [webdriver.Opera],
    "webkitgtk": [webdriver.WebKitGTK, webdriver.webkitgtk.service.Service],
    "wpewebkit": [webdriver.WPEWebKit, webdriver.wpewebkit.service.Service],
    "remote": [webdriver.Remote],
}


def set_web_driver(web_browser: str, web_driver_path=None, **kwargs):
    web_browser = str(web_browser).lower()
    web_info = webdriver_dict.get(web_browser)
    if web_browser not in ["opera", "remote"]:
        web_service = web_info[1](web_driver_path)
        web_browser = web_info[0](service=web_service)
    else:
        web_browser = web_info[0](executable_path=web_driver_path)
    if len(kwargs) > 0:
        web_browser = web_info[0](**kwargs)
    return web_browser
