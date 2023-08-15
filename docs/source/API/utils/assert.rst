Assert API
----

.. code-block:: python

    def _make_webdriver_check_dict(webdriver_to_check: WebDriver) -> dict:
        """
        use to check webdriver current info
        :param webdriver_to_check: what webdriver we want to check
        :return: webdriver detail dict
        """

.. code-block:: python

    def _make_web_element_check_dict(web_element_to_check: WebElement) -> dict:
        """
        use to check web element current info
        :param web_element_to_check: what web element we want to check
        :return: web element detail dict
        """

.. code-block:: python

    def check_value(element_name: str, element_value: typing.Any, result_check_dict: dict) -> None:
        """
        use to check state
        :param element_name: the name of element we want to check
        :param element_value: what value element should be
        :param result_check_dict: the dict include data name and value to check check_dict is valid or not
        :return: None
        """

.. code-block:: python

    def check_values(check_dict: dict, result_check_dict: dict) -> None:
        """
        :param check_dict: dict include data name and value to check
        :param result_check_dict: the dict include data name and value to check check_dict is valid or not
        :return: None
        """

.. code-block:: python

    def check_webdriver_value(element_name: str, element_value: typing.Any, webdriver_to_check: WebDriver) -> None:
        """
        :param element_name: the name of element we want to check
        :param element_value: what value element should be
        :param webdriver_to_check: the dict include data name and value to check result_dict is valid or not
        :return: None
        """

.. code-block:: python

    def check_webdriver_details(webdriver_to_check: WebDriver, result_check_dict: dict) -> None:
        """
        :param webdriver_to_check: what webdriver we want to check
        :param result_check_dict: the dict include data name and value to check result_dict is valid or not
        :return: None
        """

.. code-block:: python

    def check_web_element_value(element_name: str, element_value: typing.Any, web_element_to_check: WebElement) -> None:
        """
        :param element_name: the name of element we want to check
        :param element_value: what value element should be
        :param web_element_to_check: the dict include data name and value to check result_dict is valid or not
        :return: None
        """

.. code-block:: python

    def check_web_element_details(web_element_to_check: WebElement, result_check_dict: dict) -> None:
        """
        :param web_element_to_check: what web element we want to check
        :param result_check_dict: the dict include data name and value to check result_dict is valid or not
        :return: None
        """