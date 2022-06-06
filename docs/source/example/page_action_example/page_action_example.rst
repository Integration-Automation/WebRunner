==================
WebRunner Page Action Example
==================

.. code-block:: python

    """
    use page action we need to use webdriver wrapper
    raw use webdriver_wrapper (if we only need one instance)
    or use web_runner.webdriver_wrapper
    below is raw use
    """

    from je_web_runner import webdriver_wrapper, TestObject, Keys

    "use firefox webdriver"
    webdriver_wrapper.set_driver("firefox")
    webdriver_wrapper.to_url("https://google.com")
    """test object google input type: "name" element name: "q" """
    google_input = TestObject("q", "name")
    google_input_element = webdriver_wrapper.find_element(google_input)
    "implicitly_wait"
    webdriver_wrapper.implicitly_wait(3)
    "move to element"
    webdriver_wrapper.move_to_element(google_input_element)
     "move to element with offset"
    webdriver_wrapper.move_to_element_with_offset(google_input_element, 10, 10)
    "move by offset"
    webdriver_wrapper.move_by_offset(10, 10)
    "drag and drop a element to another element"
    webdriver_wrapper.drag_and_drop(google_input_element, google_input_element)
    "drag and drop a element to another element with offset"
    webdriver_wrapper.drag_and_drop_offset(google_input_element, 10, 10)
    "perform all action"
    webdriver_wrapper.perform()
    "mouse left click element"
    webdriver_wrapper.left_click(google_input_element)
    "release mouse"
    webdriver_wrapper.release(google_input_element)
    "mouse left click current mouse position"
    webdriver_wrapper.left_click()
    "release mouse"
    webdriver_wrapper.release()
    "mouse left click current mouse position"
    webdriver_wrapper.left_double_click()
    "release mouse"
    webdriver_wrapper.release()
    "mouse left click current mouse position then hold"
    webdriver_wrapper.left_click_and_hold()
    "release mouse"
    webdriver_wrapper.release()
    "pause action 3sec"
    webdriver_wrapper.pause(3)
    "press keyboard F1"
    webdriver_wrapper.press_key(Keys.F1)
    "release keyboard F1"
    webdriver_wrapper.release_key(Keys.F1)
    "send key F1"
    webdriver_wrapper.send_keys(Keys.F1)
    "send key F1 to web element"
    webdriver_wrapper.send_keys_to_element(google_input_element, Keys.F1)
    "perform all action"
    webdriver_wrapper.perform()
    "quit"
    webdriver_wrapper.quit()

    """
    redirect current webdriver page
    raw use webdriver_wrapper (if we only need one instance)
    or use web_runner.webdriver_wrapper
    """

    import sys

    from je_web_runner import webdriver_wrapper

    try:
        "open the firefox instance"
        "and now we are on main page"
        webdriver_wrapper.set_driver("firefox")
        "implicitly_wait 5sec"
        webdriver_wrapper.implicitly_wait(5)
        "open youtube music"
        webdriver_wrapper.to_url("https://music.youtube.com/")
        "back to main page"
        webdriver_wrapper.back()
        "refresh current page"
        webdriver_wrapper.refresh()
        "forward to youtube music"
        webdriver_wrapper.forward()
        "quit"
        webdriver_wrapper.quit()
    except Exception as error:
        print(repr(error), file=sys.stderr)
        sys.exit(1)

    """
    window size
    raw use webdriver_wrapper (if we only need one instance)
    or use web_runner.webdriver_wrapper
    """

    import sys

    from je_web_runner import webdriver_wrapper

    try:
        "open the firefox instance"
        webdriver_wrapper.set_driver("firefox")
        "minimize current instance window"
        webdriver_wrapper.minimize_window()
        "maximize current instance window"
        webdriver_wrapper.maximize_window()
        "fullscreen current instance window"
        webdriver_wrapper.fullscreen_window()
        "set current instance window size"
        webdriver_wrapper.set_window_size(500, 500)
        "set current instance window position"
        webdriver_wrapper.set_window_position(100, 100)
        "get current instance window position"
        webdriver_wrapper.get_window_position()
        "set current instance window rect"
        webdriver_wrapper.get_window_rect()
        "set current instance window rect"
        webdriver_wrapper.set_window_rect(500, 500, 500, 500)
        "quit"
        webdriver_wrapper.quit()
    except Exception as error:
        print(repr(error), file=sys.stderr)
        sys.exit(1)

    """
    switch to element
    """
    from sys import stderr

    from je_web_runner import TestObject
    from je_web_runner import webdriver_wrapper

    try:
        "set the firefox instance"
        webdriver_wrapper.set_driver("firefox")
        "get current webdriver instance"
        firefox_webdriver = webdriver_wrapper.current_webdriver
        "to google"
        webdriver_wrapper.to_url("https://www.google.com")
        """test object type: "name" element name: "q" """
        google_input = TestObject("q", "name")
        webdriver_wrapper.implicitly_wait(3)
        "now current web element is google_input"
        webdriver_wrapper.find_element(google_input)
        "return active_element"
        webdriver_wrapper.switch("active_element")
        "return parent_frame"
        webdriver_wrapper.switch("parent_frame")
        "return default_content"
        webdriver_wrapper.switch("default_content")
        webdriver_wrapper.quit()
    except Exception as error:
        print(repr(error), file=stderr)

    "webdriver screenshot"
    import sys

    from je_web_runner import webdriver_wrapper

    try:
        "set firefox instance"
        webdriver_wrapper.set_driver("firefox")
        "current page screenshot as png"
        webdriver_wrapper.get_screenshot_as_png()
        "current page screenshot as base64"
        webdriver_wrapper.get_screenshot_as_base64()
        webdriver_wrapper.quit()
    except Exception as error:
        print(repr(error), file=sys.stderr)
        sys.exit(1)

    "timeout"
    from je_web_runner import webdriver_wrapper
    "set firefox instance"
    webdriver_wrapper.set_driver("firefox")
    "implicitly_wait 5sec"
    webdriver_wrapper.implicitly_wait(5)
    "set max page load time (sec)"
    webdriver_wrapper.set_page_load_timeout(5)
    "set max script load time (sec)"
    webdriver_wrapper.set_script_timeout(5)
    "quit"
    webdriver_wrapper.quit()

    "cookies"
    import sys

    from je_web_runner import webdriver_wrapper

    try:
        "set firefox instance"
        webdriver_wrapper.set_driver("firefox")
        "open https://google.com"
        webdriver_wrapper.to_url("https://google.com")
        "add cookie name is cookie name value is cookie value"
        webdriver_wrapper.add_cookie({"name": "test_cookie_name", "value": "test_cookie_value"})
        "check cookie"
        print(webdriver_wrapper.get_cookies())
        "delete cookie"
        webdriver_wrapper.delete_cookie("test_cookie_name")
        "add cookie name is cookie name value is cookie value"
        webdriver_wrapper.add_cookie({"name": "test_cookie_name_1", "value": "test_cookie_value_1"})
        "add cookie name is cookie name value is cookie value"
        webdriver_wrapper.add_cookie({"name": "test_cookie_name_2", "value": "test_cookie_value_2"})
        "add cookie name is cookie name value is cookie value"
        print(webdriver_wrapper.get_cookies())
        "delete all cookie"
        webdriver_wrapper.delete_all_cookies()
        "get cookies to print"
        cookies = webdriver_wrapper.get_cookies()
        print(cookies)
        webdriver_wrapper.quit()
    except Exception as error:
        print(repr(error), file=sys.stderr)
        sys.exit(1)


