==================
WebRunner open browser Example
==================

.. code-block:: python

    """
    you can use webrunner manager or just webdriver wrapper
    """

    """
    you can use web runner manager to manager instance
    like open 6 browser instance and to url "http://www.python.org"
    finally use quit to close all
    <if you want to use many instance be sure have enough memory and cpu>
    """

    import sys

    from je_web_runner import get_webdriver_manager
    from je_web_runner import webdriver_wrapper

    try:
        if __name__ == "__main__":
            webdriver_manager = get_webdriver_manager("firefox")
            webdriver_wrapper.to_url("http://www.python.org")
            webdriver_manager.new_driver("firefox")
            webdriver_wrapper.to_url("http://www.python.org")
            webdriver_manager.new_driver("firefox")
            webdriver_wrapper.to_url("http://www.python.org")
            webdriver_manager.new_driver("firefox")
            webdriver_wrapper.to_url("http://www.python.org")
            webdriver_manager.new_driver("firefox")
            webdriver_wrapper.to_url("http://www.python.org")
            webdriver_manager.new_driver("firefox")
            webdriver_wrapper.to_url("http://www.python.org")
            webdriver_manager.quit()
    except Exception as error:
        print(repr(error), file=sys.stderr)
        sys.exit(1)

    """
    you can close instance if you don't want to use it again
    new driver will add on last index
    if closed will remove from index
    like [0(firefox instance), 1(chrome instance), 2(firefox instance)]
    if we remove 1 then 2 will change to 1 position
    [0(firefox instance), 1(firefox instance)]
    """
    from je_web_runner import get_webdriver_manager

    webdriver_manager = get_webdriver_manager("firefox")
    webdriver_manager.new_driver("firefox")
    webdriver_manager.close_choose_webdriver(1)
    webdriver_manager.close_choose_webdriver(0)
    webdriver_manager.quit()

    """
    or close current webdriver instance
    this example we close the last instance <position 1>
    """
    from je_web_runner import get_webdriver_manager

    webdriver_manager = get_webdriver_manager("firefox")
    webdriver_manager.new_driver("firefox")
    webdriver_manager.close_current_webdriver()
    webdriver_manager.quit()

    """
    only use webdriver wrapper
    webdriver_wrapper.current_webdriver is selenium instance
    <but this is raw use>
    """

    import sys

    from je_web_runner import webdriver_wrapper

    try:
        web_manager = webdriver_wrapper.set_driver("firefox")

        firefox_webdriver = webdriver_wrapper.current_webdriver

        firefox_webdriver.get("http://www.python.org")

        firefox_webdriver.implicitly_wait(1)

        assert firefox_webdriver.title == "Welcome to Python.org"

        web_manager.quit()
    except Exception as error:
        print(repr(error), file=sys.stderr)
        firefox_webdriver = webdriver_wrapper.current_webdriver.quit()
        sys.exit(1)