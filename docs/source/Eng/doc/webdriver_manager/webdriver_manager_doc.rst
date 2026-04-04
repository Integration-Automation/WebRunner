WebDriver Manager
=================

Overview
--------

``WebdriverManager`` manages multiple WebDriver instances for parallel browser automation.
It maintains a list of active WebDriver instances and provides methods to create, switch between, and close them.

The global instance ``web_runner`` is used internally. Access it via the factory function ``get_webdriver_manager()``.

Creating a Manager
------------------

.. code-block:: python

    from je_web_runner import get_webdriver_manager

    # Create with Chrome
    manager = get_webdriver_manager("chrome")

    # Create with Firefox and options
    manager = get_webdriver_manager("firefox", options=["--headless"])

The factory function creates a new WebDriver and returns the global ``WebdriverManager`` instance.

Managing Multiple Browsers
--------------------------

.. code-block:: python

    manager = get_webdriver_manager("chrome")

    # Add a second browser instance
    manager.new_driver("firefox")

    # Switch to Chrome (index 0)
    manager.change_webdriver(0)
    manager.webdriver_wrapper.to_url("https://example.com")

    # Switch to Firefox (index 1)
    manager.change_webdriver(1)
    manager.webdriver_wrapper.to_url("https://google.com")

    # Close Firefox only
    manager.close_choose_webdriver(1)

    # Close the current browser
    manager.close_current_webdriver()

    # Close and quit ALL browsers
    manager.quit()

Key Attributes
--------------

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Attribute
     - Type
     - Description
   * - ``webdriver_wrapper``
     - ``WebDriverWrapper``
     - Wrapper for WebDriver operations
   * - ``webdriver_element``
     - ``WebElementWrapper``
     - Wrapper for element operations
   * - ``current_webdriver``
     - ``WebDriver | None``
     - Currently active WebDriver instance

Methods
-------

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - Method
     - Parameters
     - Description
   * - ``new_driver()``
     - ``webdriver_name: str, options: List[str] = None, **kwargs``
     - Create a new WebDriver instance
   * - ``change_webdriver()``
     - ``index_of_webdriver: int``
     - Switch to a WebDriver by index
   * - ``close_current_webdriver()``
     -
     - Close the current WebDriver
   * - ``close_choose_webdriver()``
     - ``webdriver_index: int``
     - Close a WebDriver by index
   * - ``quit()``
     -
     - Close and quit all WebDrivers

.. note::

   When ``quit()`` is called, it also cleans up all saved ``TestObjectRecord`` entries.
