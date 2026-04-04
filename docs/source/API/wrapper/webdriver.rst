WebDriver API
=============

Options Configuration
---------------------

``je_web_runner.webdriver.webdriver_with_options``

.. code-block:: python

    def set_webdriver_options_argument(
        webdriver_name: str,
        argument_iterable: Union[List[str], Set[str]]
    ) -> Options:
        """
        Set browser startup arguments.

        :param webdriver_name: browser name (chrome, firefox, edge, etc.)
        :param argument_iterable: list of arguments (e.g., ["--headless", "--disable-gpu"])
        :return: configured Options object
        :raises WebRunnerOptionsWrongTypeException: if argument_iterable is wrong type
        """

    def set_webdriver_options_capability_wrapper(
        webdriver_name: str,
        key_and_vale_dict: dict
    ) -> Options:
        """
        Set browser capabilities.

        :param webdriver_name: browser name
        :param key_and_vale_dict: capabilities dict (e.g., {"acceptInsecureCerts": True})
        :return: configured Options object
        """

WebDriverWrapper
----------------

``je_web_runner.webdriver.webdriver_wrapper``

Class: WebDriverWrapper
~~~~~~~~~~~~~~~~~~~~~~~

Core WebDriver wrapper with 80+ methods.

**Attributes:**

- ``current_webdriver`` (``WebDriver | None``): active WebDriver
- ``_webdriver_name`` (``str | None``): name of current driver
- ``_action_chain`` (``ActionChains | None``): action chains instance

**Driver Setup:**

.. code-block:: python

    def set_driver(self, webdriver_name: str, webdriver_manager_option_dict: dict = None,
                   options: List[str] = None, **kwargs) -> WebDriver:
        """Start a new WebDriver instance."""

    def set_webdriver_options_capability(self, key_and_vale_dict: dict) -> Options:
        """Set capabilities on current WebDriver's options."""

**Element Finding:**

.. code-block:: python

    def find_element(self, test_object: TestObject) -> WebElement | None:
        """Find a single element using TestObject locator."""

    def find_elements(self, test_object: TestObject) -> list[WebElement] | None:
        """Find multiple elements using TestObject locator."""

    def find_element_with_test_object_record(self, element_name: str) -> WebElement | None:
        """Find element using a saved TestObjectRecord name."""

    def find_elements_with_test_object_record(self, element_name: str) -> list[WebElement] | None:
        """Find multiple elements using a saved TestObjectRecord name."""

**Wait:**

.. code-block:: python

    def implicitly_wait(self, time_to_wait: int) -> None:
    def explict_wait(self, wait_condition, timeout: int = 10, poll_frequency: float = 0.5):
    def set_script_timeout(self, timeout: int) -> None:
    def set_page_load_timeout(self, timeout: int) -> None:

**Navigation:**

.. code-block:: python

    def to_url(self, url: str) -> None:
    def forward(self) -> None:
    def back(self) -> None:
    def refresh(self) -> None:

**Context Switching:**

.. code-block:: python

    def switch(self, switch_type: str, switch_value: str = None) -> None:
        """
        Switch context. Supported types:
        active_element, default_content, frame, parent_frame, window, alert
        """

**Cookie Management:**

.. code-block:: python

    def get_cookies(self) -> list:
    def get_cookie(self, name: str) -> dict:
    def add_cookie(self, cookie_dict: dict) -> None:
    def delete_cookie(self, name: str) -> None:
    def delete_all_cookies(self) -> None:

**JavaScript:**

.. code-block:: python

    def execute(self, script: str, *args) -> Any:
    def execute_script(self, script: str, *args) -> Any:
    def execute_async_script(self, script: str, *args) -> Any:

**Mouse Actions:**

.. code-block:: python

    def left_click(self) -> None:
    def left_click_with_test_object(self, element_name: str) -> None:
    def right_click(self) -> None:
    def right_click_with_test_object(self, element_name: str) -> None:
    def left_double_click(self) -> None:
    def left_double_click_with_test_object(self, element_name: str) -> None:
    def left_click_and_hold(self) -> None:
    def left_click_and_hold_with_test_object(self, element_name: str) -> None:
    def release(self) -> None:
    def release_with_test_object(self, element_name: str) -> None:
    def move_to_element(self, element: WebElement) -> None:
    def move_to_element_with_test_object(self, element_name: str) -> None:
    def move_to_element_with_offset(self, element, offset_x: int, offset_y: int) -> None:
    def move_to_element_with_offset_and_test_object(self, element_name: str, offset_x: int, offset_y: int) -> None:
    def drag_and_drop(self, source, target) -> None:
    def drag_and_drop_with_test_object(self, source_name: str, target_name: str) -> None:
    def drag_and_drop_offset(self, element, offset_x: int, offset_y: int) -> None:
    def drag_and_drop_offset_with_test_object(self, element_name: str, offset_x: int, offset_y: int) -> None:
    def move_by_offset(self, offset_x: int, offset_y: int) -> None:

**Keyboard:**

.. code-block:: python

    def press_key(self, key) -> None:
    def press_key_with_test_object(self, key) -> None:
    def release_key(self, key) -> None:
    def release_key_with_test_object(self, key) -> None:
    def send_keys(self, keys: str) -> None:
    def send_keys_to_element(self, element, keys: str) -> None:
    def send_keys_to_element_with_test_object(self, element_name: str, keys: str) -> None:

**Action Chain:**

.. code-block:: python

    def perform(self) -> None:
    def reset_actions(self) -> None:
    def pause(self, duration: int) -> None:
    def scroll(self, offset_x: int, offset_y: int) -> None:

**Window Management:**

.. code-block:: python

    def maximize_window(self) -> None:
    def fullscreen_window(self) -> None:
    def minimize_window(self) -> None:
    def set_window_size(self, width: int, height: int) -> None:
    def set_window_position(self, x: int, y: int) -> None:
    def get_window_position(self) -> dict:
    def get_window_rect(self) -> dict:
    def set_window_rect(self, x=None, y=None, width=None, height=None) -> None:

**Screenshots & Logging:**

.. code-block:: python

    def get_screenshot_as_png(self) -> bytes:
    def get_screenshot_as_base64(self) -> str:
    def get_log(self, log_type: str) -> list:

**Validation & Quit:**

.. code-block:: python

    def check_current_webdriver(self, check_dict: dict) -> None:
        """Validate WebDriver properties against expected values."""

    def quit(self) -> None:
        """Quit the current single WebDriver."""

Global Instance
~~~~~~~~~~~~~~~

.. code-block:: python

    webdriver_wrapper_instance = WebDriverWrapper()
