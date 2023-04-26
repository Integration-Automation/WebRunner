Manager API
----

.. code-block:: python

    def new_driver(self, webdriver_name: str, **kwargs) -> None:
        """
        use to create new webdriver instance
        :param webdriver_name: which webdriver we want to use [chrome, chromium, firefox, edge, ie]
        :param kwargs: webdriver download manager param
        :return: None
        """

    def change_webdriver(self, index_of_webdriver: int) -> None:
        """
        change to target webdriver
        :param index_of_webdriver: change current webdriver to choose index webdriver
        :return: None
        """

    def close_current_webdriver(self) -> None:
        """
        close current webdriver
        :return: None
        """

    def close_choose_webdriver(self, webdriver_index: int) -> None:
        """
        close choose webdriver
        :param webdriver_index: close choose webdriver on current webdriver list
        :return: None
        """

    def quit(self) -> None:
        """
        close and quit all webdriver instance
        :return: None
        """

    def get_webdriver_manager(webdriver_name: str, **kwargs) -> WebdriverManager:
        """
        use to get webdriver instance
        :param webdriver_name: which webdriver we want to use [chrome, chromium, firefox, edge, ie]
        :param kwargs: webdriver download manager param
        :return: Webdriver manager instance
        """
