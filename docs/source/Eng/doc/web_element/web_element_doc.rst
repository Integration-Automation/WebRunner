Web Element Wrapper
===================

Overview
--------

``WebElementWrapper`` provides methods for interacting with located elements.
It operates on the currently active element set by ``find_element()`` or ``find_elements()``.

The global instance ``web_element_wrapper`` is imported from ``je_web_runner``.

Basic Interactions
------------------

.. code-block:: python

    from je_web_runner import web_element_wrapper

    web_element_wrapper.click_element()                     # Click element
    web_element_wrapper.input_to_element("Hello World")     # Type text
    web_element_wrapper.clear()                             # Clear content
    web_element_wrapper.submit()                            # Submit form

Attribute and Property Inspection
---------------------------------

.. code-block:: python

    web_element_wrapper.get_attribute("href")        # Get HTML attribute
    web_element_wrapper.get_property("checked")      # Get JS property
    web_element_wrapper.get_dom_attribute("data-id")  # Get DOM attribute

State Checks
------------

.. code-block:: python

    web_element_wrapper.is_displayed()    # Check visibility
    web_element_wrapper.is_enabled()      # Check if enabled
    web_element_wrapper.is_selected()     # Check if selected (checkbox/radio)

CSS Property
------------

.. code-block:: python

    web_element_wrapper.value_of_css_property("color")

Dropdown (Select) Handling
--------------------------

.. code-block:: python

    select = web_element_wrapper.get_select()
    # Now use Selenium's Select API:
    # select.select_by_visible_text("Option 1")
    # select.select_by_value("opt1")
    # select.select_by_index(0)

Element Screenshot
------------------

.. code-block:: python

    web_element_wrapper.screenshot("element")  # Saves as element.png

Switching Elements
------------------

When ``find_elements()`` returns multiple elements, use ``change_web_element()``
to switch the active element:

.. code-block:: python

    # After find_elements, switch to the 3rd element (index 2)
    web_element_wrapper.change_web_element(2)
    web_element_wrapper.click_element()

Element Validation
------------------

Validate element properties against expected values:

.. code-block:: python

    web_element_wrapper.check_current_web_element({
        "tag_name": "input",
        "enabled": True
    })

Key Attributes
--------------

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Attribute
     - Type
     - Description
   * - ``current_web_element``
     - ``WebElement | None``
     - Currently active element
   * - ``current_web_element_list``
     - ``List[WebElement] | None``
     - List of found elements (from ``find_elements``)

Methods Reference
-----------------

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Method
     - Parameters
     - Description
   * - ``click_element()``
     -
     - Click the current element
   * - ``input_to_element()``
     - ``input_value: str``
     - Type text into the element
   * - ``clear()``
     -
     - Clear element content
   * - ``submit()``
     -
     - Submit the form
   * - ``get_attribute()``
     - ``name: str``
     - Get HTML attribute value
   * - ``get_property()``
     - ``name: str``
     - Get JavaScript property value
   * - ``get_dom_attribute()``
     - ``name: str``
     - Get DOM attribute value
   * - ``is_displayed()``
     -
     - Check if element is visible
   * - ``is_enabled()``
     -
     - Check if element is enabled
   * - ``is_selected()``
     -
     - Check if element is selected
   * - ``value_of_css_property()``
     - ``property_name: str``
     - Get CSS property value
   * - ``screenshot()``
     - ``filename: str``
     - Take element screenshot
   * - ``change_web_element()``
     - ``element_index: int``
     - Switch active element by index
   * - ``check_current_web_element()``
     - ``check_dict: dict``
     - Validate element properties
   * - ``get_select()``
     -
     - Get Select object for dropdown
