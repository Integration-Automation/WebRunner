Quick Start
===========

This guide demonstrates the three main ways to use WebRunner.

Example 1: Direct Python API
-----------------------------

Use WebRunner's classes and functions directly in Python code.

.. code-block:: python

    from je_web_runner import TestObject
    from je_web_runner import get_webdriver_manager
    from je_web_runner import web_element_wrapper

    # Create a WebDriver manager (using Chrome)
    manager = get_webdriver_manager("chrome")

    # Navigate to a URL
    manager.webdriver_wrapper.to_url("https://www.google.com")

    # Set implicit wait
    manager.webdriver_wrapper.implicitly_wait(2)

    # Create a test object to locate the search box by name
    search_box = TestObject("q", "name")

    # Find the element
    manager.webdriver_wrapper.find_element(search_box)

    # Click and type into the element
    web_element_wrapper.click_element()
    web_element_wrapper.input_to_element("WebRunner automation")

    # Close the browser
    manager.quit()

Example 2: JSON Action List
-----------------------------

Define automation scripts as JSON action lists and execute them through the Action Executor.

.. code-block:: python

    from je_web_runner import execute_action

    actions = [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://www.google.com"}],
        ["WR_implicitly_wait", {"time_to_wait": 2}],
        ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
        ["WR_find_element", {"element_name": "q"}],
        ["WR_click_element"],
        ["WR_input_to_element", {"input_value": "WebRunner automation"}],
        ["WR_quit"]
    ]

    result = execute_action(actions)

Example 3: Execute from JSON File
-----------------------------------

Create an ``actions.json`` file:

.. code-block:: json

    [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://example.com"}],
        ["WR_quit"]
    ]

Execute it in Python:

.. code-block:: python

    from je_web_runner import execute_files

    results = execute_files(["actions.json"])

Or via CLI:

.. code-block:: bash

    python -m je_web_runner -e actions.json

Example 4: Headless Mode
--------------------------

Run browsers without a visible GUI window using headless mode.

.. code-block:: python

    from je_web_runner import get_webdriver_manager

    manager = get_webdriver_manager("chrome", options=["--headless", "--disable-gpu"])
    manager.webdriver_wrapper.to_url("https://example.com")
    title = manager.webdriver_wrapper.execute_script("return document.title")
    print(f"Page title: {title}")
    manager.quit()
