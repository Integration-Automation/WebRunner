==================
WebRunner Assert Value Doc
==================

.. code-block:: python

    def _make_webdriver_check_dict(webdriver_to_check: WebDriver) -> dict:
        """
        :param webdriver_to_check: what webdriver we want to check
        :return: webdriver detail dict
        """


    def _make_web_element_check_dict(web_element_to_check: WebElement) -> dict:
        """
        :param web_element_to_check: what web element we want to check
        :return: web element detail dict
        """



    def check_value(check_dict: dict, result_check_dict: dict) -> None:
        """
        :param check_dict: dict include data name and value to check
        :param result_check_dict: the dict include data name and value to check check_dict is valid or not
        :return: None
        """


    def check_webdriver(webdriver_to_check: WebDriver, result_check_dict: dict) -> None:
        """
        :param webdriver_to_check: what webdriver we want to check
        :param result_check_dict: the dict include data name and value to check result_dict is valid or not
        :return: None
        """


    def check_web_element(web_element_to_check: WebElement, result_check_dict: dict) -> None:
        """
        :param web_element_to_check: what web element we want to check
        :param result_check_dict: the dict include data name and value to check result_dict is valid or not
        :return: None
        """


