==================
WebRunner WebElement Wrapper Doc
==================

.. code-block:: python

    def submit(self) -> None:
    """
    current web element submit
    :return: None
    """

    def clear(self) -> None:
    """
    current web element clear
    :return: None
    """

    def get_property(self, name) -> str:
    """
    :param name: name of property
    :return: property value as str
    """

    def get_dom_attribute(self, name) -> str:
    """
    :param name: name of dom
    :return: dom attribute value as str
    """

    def get_attribute(self, name) -> str:
    """
    :param name: name of web element
    :return:web element attribute value as str
    """

    def is_selected(self) -> bool:
    """
    check current web element is selected or not
    :return: True or False
    """

    def is_enabled(self) -> bool:
    """
    check current web element is enable or not
    :return: True or False
    """

    def input_to_element(self, input_value) -> None:
    """
    input value to current web element
    :param input_value: what value we want to input to current web element
    :return: None
    """

    def click_element(self) -> None:
    """
    click current web element
    :return: None
    """

    def is_displayed(self) -> bool:
    """
    check current web element is displayed or not
    :return: True or False
    """

    def value_of_css_property(self, property_name) -> str:
    """
    :param property_name: name of property
    :return: css property value as str
    """

    def screenshot(self, filename) -> bool:
    """
    :param filename: full file name not need .png extension
    :return: Save True or not
    """

    def change_web_element(self, element_index: int) -> None:
    """
    :param element_index: change to web element index
    :return: web element list [element_index]
    """

    def check_current_web_element(self, check_dict: dict) -> None:
    """
    :param check_dict: check web element dict {name: should be value}
    :return: None
    """

    def get_select(self) -> Select:
    """
    get Select(current web element)
    :return: Select(current web element)
    """