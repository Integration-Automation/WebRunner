==================
WebRunner Web element Example
==================

.. code-block:: python

    """
    multi instance find element and click
    """
    import sys

    from je_web_runner import TestObject
    from je_web_runner import get_webdriver_manager
    from je_web_runner import web_element_wrapper
    from je_web_runner import webdriver_wrapper

    try:
        """
        get webdriver manager
        """
        driver_wrapper = get_webdriver_manager("firefox")
        "to google main page"
        driver_wrapper.webdriver_wrapper.to_url("https://www.google.com")
        """test object type: "name" name: "q" """
        google_input = TestObject("q", "name")
        "implicitly_wait 5sec"
        driver_wrapper.webdriver_wrapper.implicitly_wait(5)
        """current web element is google input type: "name" name: "q" """
        webdriver_wrapper.find_element(google_input)
        "click current web element"
        web_element_wrapper.click_element()
        "input to current web element"
        web_element_wrapper.input_to_element("abc_test")
        "create second firefox instance"
        driver_wrapper.new_driver("firefox")
        "change to first instance"
        driver_wrapper.change_webdriver(0)
        """current web element is google input type: "name" name: "q" """
        webdriver_wrapper.find_element(google_input)
        "input to current web element"
        web_element_wrapper.input_to_element("123")
        "change to second instance"
        driver_wrapper.change_webdriver(1)
        "to google main page"
        webdriver_wrapper.to_url("https://www.google.com")
        "implicitly_wait 5sec"
        webdriver_wrapper.implicitly_wait(5)
        """current web element is google input type: "name" name: "q" """
        webdriver_wrapper.find_element(google_input)
        "input to current web element"
        web_element_wrapper.input_to_element("123")
        "quit"
        driver_wrapper.quit()
    except Exception as error:
        print(repr(error), file=sys.stderr)
        sys.exit(1)

