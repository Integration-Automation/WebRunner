Assert API
==========

``je_web_runner.utils.assert_value.result_check``

Functions for validating WebDriver and WebElement properties.
Raises ``WebRunnerAssertException`` on validation failure.

.. code-block:: python

    def _make_webdriver_check_dict(webdriver_to_check: WebDriver) -> dict:
        """
        Build a dictionary of the WebDriver's current state for validation.

        :param webdriver_to_check: WebDriver instance to inspect
        :return: dict of WebDriver properties (name, title, current_url, etc.)
        """

.. code-block:: python

    def _make_web_element_check_dict(web_element_to_check: WebElement) -> dict:
        """
        Build a dictionary of the WebElement's current state for validation.

        :param web_element_to_check: WebElement instance to inspect
        :return: dict of WebElement properties (tag_name, text, enabled, displayed, etc.)
        """

.. code-block:: python

    def check_value(element_name: str, element_value: Any, result_check_dict: dict) -> None:
        """
        Check a single value against a result dictionary.

        :param element_name: key to look up in result_check_dict
        :param element_value: expected value
        :param result_check_dict: dictionary of actual values
        :raises WebRunnerAssertException: if values don't match
        """

.. code-block:: python

    def check_values(check_dict: dict, result_check_dict: dict) -> None:
        """
        Check multiple key-value pairs against a result dictionary.

        :param check_dict: dict of {name: expected_value} pairs
        :param result_check_dict: dictionary of actual values
        :raises WebRunnerAssertException: if any value doesn't match
        """

.. code-block:: python

    def check_webdriver_value(element_name: str, element_value: Any, webdriver_to_check: WebDriver) -> None:
        """
        Check a single WebDriver property against an expected value.

        :param element_name: property name (e.g., "name", "title")
        :param element_value: expected value
        :param webdriver_to_check: WebDriver instance to validate
        """

.. code-block:: python

    def check_webdriver_details(webdriver_to_check: WebDriver, result_check_dict: dict) -> None:
        """
        Validate multiple WebDriver properties.

        :param webdriver_to_check: WebDriver instance to validate
        :param result_check_dict: dict of {property: expected_value}
        """

.. code-block:: python

    def check_web_element_value(element_name: str, element_value: Any, web_element_to_check: WebElement) -> None:
        """
        Check a single WebElement property against an expected value.

        :param element_name: property name (e.g., "tag_name", "enabled")
        :param element_value: expected value
        :param web_element_to_check: WebElement instance to validate
        """

.. code-block:: python

    def check_web_element_details(web_element_to_check: WebElement, result_check_dict: dict) -> None:
        """
        Validate multiple WebElement properties.

        :param web_element_to_check: WebElement instance to validate
        :param result_check_dict: dict of {property: expected_value}
        """
