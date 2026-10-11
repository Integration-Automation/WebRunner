Executor API
============

``je_web_runner.utils.executor.action_executor``

Class: Executor
---------------

The action execution engine that maps command strings to callable functions. It is a
``je_action_core.ActionExecutor``: the core runs the list, keys and prints the records and holds the
commands; WebRunner adds its action format, the command gates, the retry policy, the action span and the
failure screenshots and traces.

.. code-block:: python

    class Executor(ActionExecutor):

        event_dict: dict
            # Maps command names (str) to callable functions.
            # Includes all WR_* commands and the SAFE_BUILTINS allowlist of Python built-ins.

        def execute_action(self, action_list: Union[list, dict]) -> dict:
            """
            Execute a sequence of actions and print each record's key and value.

            :param action_list: list of actions or dict with "webdriver_wrapper" key
                Format: [["command", {params}], ["command"], ...]; an empty list runs nothing
            :return: dict mapping "execute: <action>" (repeats numbered " #2", " #3" ...) to the return
                value, or to the error text (with any failure screenshot or trace) when the action failed
            :raises WebRunnerExecuteException: if action_list is not a list or a dict holding one
            """

        def collect_action_results(self, action_list: Union[list, dict]) -> tuple[dict, list[str]]:
            """
            Like execute_action, but prints nothing; also returns the keys of the actions that failed.
            """

        def execute_one(self, action: list) -> Any:
            """
            Run one action through the same gates, retries and span and return its value.

            :raises WebRunnerExecuteException: when it is malformed or fails (the original error is __cause__)
            """

        def execute_files(self, execute_files_list: list) -> list:
            """
            Execute actions from JSON files.

            :param execute_files_list: list of file paths to JSON action files
            :return: list of execution result dicts (one per file)
            """

        def attempt(self, action: list):
            """
            Run one action under the retry policy and the action span; every action of a list passes here.
            """

        def _execute_event(self, action: list):
            """
            Execute a single action once: refused commands and the arbitrary-script gate first, then the lookup.

            :param action: ["command_name"], ["command_name", {kwargs}], ["command_name", [args]]
                or ["command_name", [args], {kwargs}]
            :return: return value of the executed function
            :raises WebRunnerExecuteException: if the command is refused, not found, or the format is invalid
            """

Registered Commands (event_dict)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**WebDriver Manager:**
``WR_get_webdriver_manager``, ``WR_change_index_of_webdriver``, ``WR_quit``

**Test Object:**
``WR_SaveTestObject``, ``WR_CleanTestObject``

**WebDriver Wrapper (Navigation):**
``WR_to_url``, ``WR_forward``, ``WR_back``, ``WR_refresh``, ``WR_switch``

**WebDriver Wrapper (Element Finding):**
``WR_find_element``, ``WR_find_elements``

**WebDriver Wrapper (Wait):**
``WR_implicitly_wait``, ``WR_explict_wait``, ``WR_set_script_timeout``, ``WR_set_page_load_timeout``

**WebDriver Wrapper (Cookies):**
``WR_get_cookies``, ``WR_get_cookie``, ``WR_add_cookie``, ``WR_delete_cookie``, ``WR_delete_all_cookies``

**WebDriver Wrapper (JavaScript):**
``WR_execute``, ``WR_execute_script``, ``WR_execute_async_script``

**WebDriver Wrapper (Mouse):**
``WR_left_click``, ``WR_right_click``, ``WR_left_double_click``,
``WR_left_click_and_hold``, ``WR_release``,
``WR_move_to_element``, ``WR_move_to_element_with_offset``, ``WR_move_by_offset``,
``WR_drag_and_drop``, ``WR_drag_and_drop_offset``

**WebDriver Wrapper (Keyboard):**
``WR_press_key``, ``WR_release_key``, ``WR_send_keys``, ``WR_send_keys_to_element``

**WebDriver Wrapper (Actions):**
``WR_perform``, ``WR_reset_actions``, ``WR_pause``, ``WR_scroll``

**WebDriver Wrapper (Window):**
``WR_maximize_window``, ``WR_fullscreen_window``, ``WR_minimize_window``,
``WR_set_window_size``, ``WR_set_window_position``, ``WR_get_window_position``,
``WR_get_window_rect``, ``WR_set_window_rect``

**WebDriver Wrapper (Screenshot/Log):**
``WR_get_screenshot_as_png``, ``WR_get_screenshot_as_base64``, ``WR_get_log``

**WebDriver Wrapper (Other):**
``WR_set_driver``, ``WR_set_webdriver_options_capability``,
``WR_check_current_webdriver``, ``WR_single_quit``

**Web Element:**
``WR_click_element``, ``WR_input_to_element``,
``WR_element_submit``, ``WR_element_clear``,
``WR_element_get_property``, ``WR_element_get_dom_attribute``, ``WR_element_get_attribute``,
``WR_element_is_selected``, ``WR_element_is_enabled``, ``WR_element_is_displayed``,
``WR_element_value_of_css_property``, ``WR_element_screenshot``,
``WR_element_change_web_element``, ``WR_element_check_current_web_element``,
``WR_element_get_select``

**Test Record:**
``WR_set_record_enable``

**Report Generation:**
``WR_generate_html``, ``WR_generate_html_report``,
``WR_generate_json``, ``WR_generate_json_report``,
``WR_generate_xml``, ``WR_generate_xml_report``

**Nested Execution:**
``WR_execute_action``, ``WR_execute_files``

**Package Management:**
``WR_add_package_to_executor``, ``WR_add_package_to_callback_executor``

**Python Built-ins:**
Only the ``SAFE_BUILTINS`` allowlist shared with the other frameworks: ``abs``, ``all``, ``any``, ``ascii``,
``bin``, ``callable``, ``chr``, ``divmod``, ``format``, ``hash``, ``hex``, ``len``, ``max``, ``min``, ``oct``,
``ord``, ``pow``, ``print``, ``repr``, ``round``, ``sorted``, ``sum``

Module-level Functions
----------------------

.. code-block:: python

    def add_command_to_executor(command_dict: dict) -> None:
        """
        Dynamically add commands to the global Executor.

        :param command_dict: {command_name: function}
        :raises WebRunnerAddCommandException: if value is not a function/method
        """

    def execute_action(action_list: list) -> dict:
        """Global convenience function to execute actions."""

    def execute_files(execute_files_list: list) -> list:
        """Global convenience function to execute actions from files."""

Global Instance
---------------

.. code-block:: python

    executor = Executor()
