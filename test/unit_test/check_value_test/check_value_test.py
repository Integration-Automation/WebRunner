from sys import stderr

from je_web_runner import webdriver_wrapper, TestObject, web_element_wrapper


webdriver_wrapper.set_driver("firefox")
firefox_webdriver = webdriver_wrapper.current_webdriver
webdriver_wrapper.to_url("http://www.python.org")
webdriver_wrapper.implicitly_wait(3)
webdriver_wrapper.check_current_webdriver(
    {
        "title": "Welcome to Python.org"
     }
)
try:
    webdriver_wrapper.check_current_webdriver(
        {
            "title": "this should be raise exception"
        }
    )
except Exception as error:
    print(repr(error), file=stderr)


google_input = TestObject("q", "name")
webdriver_wrapper.implicitly_wait(3)
webdriver_wrapper.find_element(google_input)
web_element_wrapper.check_current_web_element(
    {
        "tag_name": web_element_wrapper.current_web_element.tag_name,
        "text": web_element_wrapper.current_web_element.text,
        "location_once_scrolled_into_view": web_element_wrapper.current_web_element.location_once_scrolled_into_view,
        "size": web_element_wrapper.current_web_element.size,
        "location": web_element_wrapper.current_web_element.location,
        "parent": web_element_wrapper.current_web_element.parent,
        "id": web_element_wrapper.current_web_element.id,
     }
)

webdriver_wrapper.quit()
