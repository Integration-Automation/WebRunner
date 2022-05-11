from selenium.webdriver.remote.webelement import WebElement


class WebElementWrapper(object):

    def __init__(self):
        self.current_web_element: [WebElement, None] = None

    def input_to_element(self, input_value):
        self.current_web_element.send_keys(input_value)

    def click_element(self):
        self.current_web_element.click()


web_element_wrapper = WebElementWrapper()
