Manager API
===========

``je_web_runner.manager.webrunner_manager``

Class: WebdriverManager
-----------------------

Manages multiple WebDriver instances for parallel browser automation.

**Attributes:**

- ``webdriver_wrapper`` (``WebDriverWrapper``): WebDriver operations wrapper
- ``webdriver_element`` (``WebElementWrapper``): element operations wrapper
- ``current_webdriver`` (``WebDriver | None``): currently active WebDriver

**Methods:**

.. code-block:: python

    def new_driver(self, webdriver_name: str, options: List[str] = None, **kwargs) -> None:
        """
        Create a new WebDriver instance and add it to the managed list.

        :param webdriver_name: browser name [chrome, chromium, firefox, edge, ie]
        :param options: browser startup arguments (e.g., ["--headless"])
        :param kwargs: additional parameters passed to set_driver()
        """

    def change_webdriver(self, index_of_webdriver: int) -> None:
        """
        Switch the active WebDriver to the one at the given index.

        :param index_of_webdriver: index in the internal WebDriver list
        """

    def close_current_webdriver(self) -> None:
        """Close and remove the currently active WebDriver."""

    def close_choose_webdriver(self, webdriver_index: int) -> None:
        """
        Close a specific WebDriver by index.

        :param webdriver_index: index in the internal WebDriver list
        """

    def quit(self) -> None:
        """
        Close and quit ALL managed WebDriver instances.
        Also cleans up all TestObjectRecord entries.
        """

Factory Function
----------------

.. code-block:: python

    def get_webdriver_manager(webdriver_name: str, **kwargs) -> WebdriverManager:
        """
        Get the global WebdriverManager and create a new driver.

        :param webdriver_name: browser name [chrome, chromium, firefox, edge, ie]
        :param kwargs: additional parameters (e.g., options)
        :return: global WebdriverManager instance
        """

Global Instance
---------------

.. code-block:: python

    web_runner = WebdriverManager()
