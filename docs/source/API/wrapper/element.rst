Element API
===========

``je_web_runner.element.web_element_wrapper``

Class: WebElementWrapper
------------------------

Wraps Selenium WebElement with convenience methods for interaction and validation.

**Attributes:**

- ``current_web_element`` (``WebElement | None``): currently active element
- ``current_web_element_list`` (``List[WebElement] | None``): list of found elements

**Methods:**

.. code-block:: python

    def click_element(self) -> None:
        """Click the current WebElement."""

    def input_to_element(self, input_value: str) -> None:
        """Type text into the current WebElement via send_keys."""

    def clear(self) -> None:
        """Clear the content of the current WebElement."""

    def submit(self) -> None:
        """Submit the current WebElement's form."""

    def get_attribute(self, name: str) -> str | None:
        """Get an HTML attribute value."""

    def get_property(self, name: str) -> None | str | bool | WebElement | dict:
        """Get a JavaScript property value."""

    def get_dom_attribute(self, name: str) -> str | None:
        """Get a DOM attribute value."""

    def is_displayed(self) -> bool | None:
        """Check if the element is visible."""

    def is_enabled(self) -> bool | None:
        """Check if the element is enabled."""

    def is_selected(self) -> bool | None:
        """Check if the element is selected (checkbox/radio)."""

    def value_of_css_property(self, property_name: str) -> str | None:
        """Get a CSS property value."""

    def screenshot(self, filename: str) -> bool | None:
        """Take a screenshot of the element. Saves as {filename}.png."""

    def change_web_element(self, element_index: int) -> None:
        """Switch active element to one from current_web_element_list by index."""

    def check_current_web_element(self, check_dict: dict) -> None:
        """
        Validate the current WebElement's properties.
        :param check_dict: {property_name: expected_value}
        :raises WebRunnerAssertException: if validation fails
        """

    def get_select(self) -> Select | None:
        """Get a Selenium Select wrapper for dropdown elements."""

Global Instance
---------------

.. code-block:: python

    web_element_wrapper = WebElementWrapper()
