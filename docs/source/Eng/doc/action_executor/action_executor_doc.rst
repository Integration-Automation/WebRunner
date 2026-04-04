Action Executor
===============

Overview
--------

The Action Executor is a powerful engine that maps command strings to callable functions.
It allows you to define automation scripts as JSON action lists, enabling data-driven automation workflows.

The executor also includes all Python built-in functions, so you can call ``print``, ``len``, etc. from action lists.

Action Format
-------------

Each action is a list with the command name and optional parameters:

.. code-block:: python

    ["command_name"]                        # No parameters
    ["command_name", {"key": "value"}]      # Keyword arguments
    ["command_name", [arg1, arg2]]          # Positional arguments

Basic Usage
-----------

.. code-block:: python

    from je_web_runner import execute_action

    actions = [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://www.google.com"}],
        ["WR_implicitly_wait", {"time_to_wait": 2}],
        ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
        ["WR_find_element", {"element_name": "q"}],
        ["WR_click_element"],
        ["WR_input_to_element", {"input_value": "WebRunner"}],
        ["WR_quit"]
    ]

    result = execute_action(actions)

The ``execute_action()`` function returns a dict mapping each action to its return value.

Available Commands
------------------

**WebDriver Manager:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_get_webdriver_manager``
     - Create a new WebDriver (params: ``webdriver_name``, ``options``)
   * - ``WR_change_index_of_webdriver``
     - Switch to a WebDriver by index
   * - ``WR_quit``
     - Quit all WebDrivers
   * - ``WR_single_quit``
     - Quit the current single WebDriver

**Navigation:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_to_url``
     - Navigate to URL (param: ``url``)
   * - ``WR_forward``
     - Go forward
   * - ``WR_back``
     - Go back
   * - ``WR_refresh``
     - Refresh the page

**Element Finding:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_find_element``
     - Find single element by saved test object name (param: ``element_name``)
   * - ``WR_find_elements``
     - Find multiple elements by saved test object name

**Wait:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_implicitly_wait``
     - Set implicit wait (param: ``time_to_wait``)
   * - ``WR_explict_wait``
     - Explicit wait with condition
   * - ``WR_set_script_timeout``
     - Set script timeout
   * - ``WR_set_page_load_timeout``
     - Set page load timeout

**Mouse Actions:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_left_click``
     - Left click (on saved test object or current position)
   * - ``WR_right_click``
     - Right click
   * - ``WR_left_double_click``
     - Double click
   * - ``WR_left_click_and_hold``
     - Click and hold
   * - ``WR_release``
     - Release held button
   * - ``WR_drag_and_drop``
     - Drag from source to target (test object names)
   * - ``WR_drag_and_drop_offset``
     - Drag to offset
   * - ``WR_move_to_element``
     - Hover over element (test object name)
   * - ``WR_move_to_element_with_offset``
     - Hover with offset
   * - ``WR_move_by_offset``
     - Move mouse by offset

**Keyboard:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_press_key``
     - Press a key
   * - ``WR_release_key``
     - Release a key
   * - ``WR_send_keys``
     - Send keys globally
   * - ``WR_send_keys_to_element``
     - Send keys to saved test object

**Action Chain:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_perform``
     - Execute queued actions
   * - ``WR_reset_actions``
     - Clear action queue
   * - ``WR_pause``
     - Pause in chain
   * - ``WR_scroll``
     - Scroll page

**Cookies:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_get_cookies``
     - Get all cookies
   * - ``WR_get_cookie``
     - Get a specific cookie
   * - ``WR_add_cookie``
     - Add a cookie
   * - ``WR_delete_cookie``
     - Delete a cookie
   * - ``WR_delete_all_cookies``
     - Delete all cookies

**JavaScript:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_execute``
     - Execute JavaScript
   * - ``WR_execute_script``
     - Execute script
   * - ``WR_execute_async_script``
     - Execute async script

**Window:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_maximize_window``
     - Maximize window
   * - ``WR_minimize_window``
     - Minimize window
   * - ``WR_fullscreen_window``
     - Full screen
   * - ``WR_set_window_size``
     - Set window size
   * - ``WR_set_window_position``
     - Set window position
   * - ``WR_get_window_position``
     - Get window position
   * - ``WR_get_window_rect``
     - Get window rect
   * - ``WR_set_window_rect``
     - Set window rect

**Screenshot & Logging:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_get_screenshot_as_png``
     - Get screenshot as PNG bytes
   * - ``WR_get_screenshot_as_base64``
     - Get screenshot as base64
   * - ``WR_get_log``
     - Get browser logs

**Element Interaction:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_click_element``
     - Click the current element
   * - ``WR_input_to_element``
     - Type text into element
   * - ``WR_element_clear``
     - Clear element content
   * - ``WR_element_submit``
     - Submit form
   * - ``WR_element_get_attribute``
     - Get element attribute
   * - ``WR_element_get_property``
     - Get element property
   * - ``WR_element_get_dom_attribute``
     - Get DOM attribute
   * - ``WR_element_is_displayed``
     - Check if element is visible
   * - ``WR_element_is_enabled``
     - Check if element is enabled
   * - ``WR_element_is_selected``
     - Check if element is selected
   * - ``WR_element_value_of_css_property``
     - Get CSS property
   * - ``WR_element_screenshot``
     - Take element screenshot
   * - ``WR_element_change_web_element``
     - Switch active element
   * - ``WR_element_check_current_web_element``
     - Validate element properties
   * - ``WR_element_get_select``
     - Get Select for dropdown

**Test Object:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_SaveTestObject``
     - Save a test object (params: ``test_object_name``, ``object_type``)
   * - ``WR_CleanTestObject``
     - Clear all saved test objects

**Report:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_generate_html``
     - Generate HTML report string
   * - ``WR_generate_html_report``
     - Save HTML report to file
   * - ``WR_generate_json``
     - Generate JSON report dicts
   * - ``WR_generate_json_report``
     - Save JSON report to file
   * - ``WR_generate_xml``
     - Generate XML report
   * - ``WR_generate_xml_report``
     - Save XML report to file

**Other:**

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Command
     - Description
   * - ``WR_switch``
     - Switch context (frame, window, alert)
   * - ``WR_check_current_webdriver``
     - Validate WebDriver properties
   * - ``WR_set_record_enable``
     - Enable/disable test recording
   * - ``WR_execute_action``
     - Nested execute action list
   * - ``WR_execute_files``
     - Execute from JSON files
   * - ``WR_add_package_to_executor``
     - Add a Python package to executor
   * - ``WR_add_package_to_callback_executor``
     - Add a Python package to callback executor

Execute from JSON Files
-----------------------

.. code-block:: python

    from je_web_runner import execute_files

    # Execute actions from multiple JSON files
    results = execute_files(["actions1.json", "actions2.json"])

JSON file format:

.. code-block:: json

    [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://example.com"}],
        ["WR_quit"]
    ]

Dict Format Input
-----------------

The executor also accepts a dict with a ``"webdriver_wrapper"`` key:

.. code-block:: python

    execute_action({
        "webdriver_wrapper": [
            ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
            ["WR_quit"]
        ]
    })

Add Custom Commands
-------------------

Register your own functions as executor commands:

.. code-block:: python

    from je_web_runner import add_command_to_executor

    def my_custom_function(param1, param2):
        print(f"Custom: {param1}, {param2}")

    add_command_to_executor({"my_command": my_custom_function})

    # Now use it in action lists
    execute_action([
        ["my_command", {"param1": "hello", "param2": "world"}]
    ])

.. note::

   Only ``types.MethodType`` and ``types.FunctionType`` are accepted.
   Passing other callable types will raise ``WebRunnerAddCommandException``.
