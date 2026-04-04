Assertion and Validation
========================

Overview
--------

WebRunner provides assertion utilities for validating WebDriver and WebElement states
during automation. If a check fails, a ``WebRunnerAssertException`` is raised.

WebDriver Validation
--------------------

Validate properties of the current WebDriver:

.. code-block:: python

    # Via WebDriverWrapper
    wrapper.check_current_webdriver({"name": "chrome"})

.. code-block:: python

    # Via utility functions
    from je_web_runner.utils.assert_value.result_check import (
        check_webdriver_value,
        check_webdriver_values,
    )

    check_webdriver_value("name", "chrome", webdriver_instance)
    check_webdriver_values({"name": "chrome"}, webdriver_instance)

WebElement Validation
---------------------

Validate properties of the current WebElement:

.. code-block:: python

    # Via WebElementWrapper
    web_element_wrapper.check_current_web_element({
        "tag_name": "input",
        "enabled": True
    })

.. code-block:: python

    # Via utility functions
    from je_web_runner.utils.assert_value.result_check import check_web_element_details

    check_web_element_details(element, {
        "tag_name": "input",
        "enabled": True
    })

General Value Checking
----------------------

.. code-block:: python

    from je_web_runner.utils.assert_value.result_check import check_value, check_values

    # Check a single value against a result dictionary
    check_value("element_name", "expected_value", result_check_dict)

    # Check multiple values
    check_values({"name": "expected"}, result_check_dict)

Via Action Executor
-------------------

.. code-block:: python

    from je_web_runner import execute_action

    execute_action([
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_check_current_webdriver", {"check_dict": {"name": "chrome"}}],
        ["WR_quit"],
    ])

Functions Reference
-------------------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Function
     - Description
   * - ``check_value(element_name, element_value, result_check_dict)``
     - Check a single value against a result dictionary
   * - ``check_values(check_dict, result_check_dict)``
     - Check multiple key-value pairs
   * - ``check_webdriver_value(element_name, element_value, webdriver)``
     - Check a single WebDriver property
   * - ``check_webdriver_values(check_dict, webdriver)``
     - Check multiple WebDriver properties (alias: ``check_webdriver_details``)
   * - ``check_web_element_details(element, check_dict)``
     - Validate WebElement properties against expected values
