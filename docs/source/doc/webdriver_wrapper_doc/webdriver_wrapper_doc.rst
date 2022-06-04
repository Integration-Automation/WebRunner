==================
Webrunner WebDriver Wrapper Doc
==================

.. code-block:: python

     def set_driver(self, webdriver_name: str, opera_path: str = None,
                   webdriver_manager_option_dict: dict = None, **kwargs) -> \
            Union[
            webdriver.Chrome,
            webdriver.Chrome,
            webdriver.Firefox,
            webdriver.Opera,
            webdriver.Edge,
            webdriver.Ie,
            webdriver.Safari,
            ]:
        """
        :param webdriver_name: which webdriver we want to use
        :param opera_path: if you are use opera you need to set this var
        :param webdriver_manager_option_dict: if you want to set webdriver download manager
        :param kwargs: used to catch var
        :return: current use webdriver
        """

      def set_webdriver_options_capability(self, key_and_vale_dict: dict) -> \
        Union[
        webdriver.Chrome,
        webdriver.Chrome,
        webdriver.Firefox,
        webdriver.Opera,
        webdriver.Edge,
        webdriver.Ie,
        webdriver.Safari,
        ]:
        """
        :param key_and_vale_dict: use to set webdriver capability
        :return: current webdriver
        """

        def find_element(self, test_object: TestObject) -> WebElement:
        """
        :param test_object: use test object to find element
        :return: fined web element
        """

        def find_element(self, test_object: TestObject) -> WebElement:
        """
        :param test_object: use test object to find element
        :return: fined web element
        """

        def find_elements(self, test_object: TestObject) -> List[WebElement]:
        """
        :param test_object: use test object to find elements
        :return: list include fined web element
        """

        def find_element_with_test_object_record(self, element_name: str) -> WebElement:
        """
        this is executor use but still can normal use
        :param element_name: test object name
        :return: fined web element
        """

        def find_elements_with_test_object_record(self, element_name: str) -> List[WebElement]:
        """
        this is executor use but still can normal use
        :param element_name: test object name
        :return: list include fined web element
        """

        def implicitly_wait(self, time_to_wait: int) -> None:
        """
        :param time_to_wait: how much time we want to wait
        :return: None
        """

        def explict_wait(self, wait_time: int, statement: bool, until_type: bool = True):
        """
        :param wait_time: how much time we want to wait if over-time will raise an exception
        :param statement: a program statement should be return True or False
        :param until_type: what type until wait True is until False is until_not
        :return:
        """

        def to_url(self, url: str) -> None:
        """
        :param url: what url we want redirect to
        :return: None
        """

        def forward(self) -> None:
        """
        forward current page
        :return: None
        """

        def back(self) -> None:
        """
        back current page
        :return: None
        """

        def refresh(self) -> None:
        """
        refresh current page
        :return: None
        """

        def switch(self, switch_type: str, switch_target_name: str = None):
        """
        :param switch_type: what type switch? one of  [active_element, default_content, frame,
        parent_frame, window, alert]
        :param switch_target_name: what target we want to switch use name to search
        :return: what we switch to
        """

        def set_script_timeout(self, time_to_wait) -> None:
        """
        set max script execute time
        :param time_to_wait: how much time we want to wait if over-time will raise an exception
        :return: None
        """

        def set_page_load_timeout(self, time_to_wait) -> None:
        """
        set page load max wait time
        :param time_to_wait: how much time we want to wait if over-time will raise an exception
        :return: None
        """

        def get_cookies(self) -> List[dict]:
        """
        get current page cookies
        :return: cookies as list
        """

        def get_cookie(self, name) -> dict:
        """
        use to get current page cookie
        :param name: use cookie name to find cookie
        :return: {cookie_name: value}
        """

        def add_cookie(self, cookie_dict: dict) -> None:
        """
        use to add cookie to current page
        :param cookie_dict: {cookie_name: value}
        :return: None
        """

        def delete_cookie(self, name) -> None:
        """
        use to delete current page cookie
        :param name: use name to find cookie
        :return: None
        """

        def delete_all_cookies(self) -> None:
        """
        delete current page all cookies
        :return: None
        """

        def execute(self, driver_command: str, params: dict = None) -> dict:
        """
        :param driver_command: webdriver command
        :param params: webdriver command params
        :return: after execute dict
        """

        def execute_script(self, script, *args) -> None:
        """
        execute script
        :param script: script to execute
        :param args: script args
        :return: None
        """

        def execute_async_script(self, script: str, *args):
        """
        execute script async
        :param script:script to execute
        :param args: script args
        :return: None
        """

        def move_to_element(self, targe_element: WebElement) -> None:
        """
        move mouse to target web element
        :param targe_element: target web element
        :return: None
        """

        def move_to_element_with_test_object(self, element_name: str):
        """
        move mouse to target web element use test object
        :param element_name: target web element  name
        :return: None
        """

        def move_to_element_with_offset(self, target_element: WebElement, x: int, y: int) -> None:
            """
            move to target element with offset
            :param target_element: what target web element we want to move to
            :param x: offset x
            :param y: offset y
            :return: None
            """

        def move_to_element_with_offset_and_test_object(self, element_name: str, x: int, y: int) -> None:
            """
            move to target element with offset use test object
            :param element_name: test object name
            :param x: offset x
            :param y: offset y
            :return: None
            """

        def drag_and_drop(self, web_element: WebElement, targe_element: WebElement) -> None:
        """
        drag web element to target element then drop
        :param web_element: which web element we want to drag and drop
        :param targe_element: target web element to drop
        :return: None
        """

        def drag_and_drop_with_test_object(self, element_name: str, target_element_name: str):
        """
        drag web element to target element then drop use testobject
        :param element_name: which web element we want to drag and drop use name to find
        :param target_element_name: target web element to drop use name to find
        :return: None
        """

        def drag_and_drop_offset(self, web_element: WebElement, offset_x: int, offset_y: int) -> None:
        """
        drag web element to target element then drop with offset
        :param web_element: which web element we want to drag and drop with offset
        :param offset_x: offset x
        :param offset_y: offset y
        :return: None
        """

        def drag_and_drop_offset_with_test_object(self, element_name: str, offset_x: int, offset_y: int) -> None:
        """
        drag web element to target element then drop with offset and test object
        :param element_name: test object name
        :param offset_x: offset x
        :param offset_y: offset y
        :return: None
        """

        def perform(self) -> None:
        """
        perform actions
        :return: None
        """

        def reset_actions(self) -> None:
        """
        clear actions
        :return: None
        """

        def left_click(self, on_element: WebElement = None) -> None:
        """
        left click mouse on current mouse position or click on web element
        :param on_element: can be None or web element
        :return: None
        """

        def left_click_with_test_object(self, element_name: str = None) -> None:
        """
        left click mouse on current mouse position or click on web element
        find use test object name
        :param element_name: test object name
        :return: None
        """

        def left_click_and_hold(self, on_element: WebElement = None) -> None:
        """
        left click and hold on current mouse position or left click and hold on web element
        :param on_element: can be None or web element
        :return: None
        """

        def left_click_and_hold_with_test_object(self, element_name: str = None) -> None:
        """
        left click and hold on current mouse position or left click and hold on web element
        find use test object name
        :param element_name: test object name
        :return: None
        """

        def right_click(self, on_element: WebElement = None) -> None:
        """
        right click mouse on current mouse position or click on web element
        :param on_element: can be None or web element
        :return: None
        """

        def right_click_with_test_object(self, element_name: str = None) -> None:
        """
        right click mouse on current mouse position or click on web element
        find use test object name
        :param element_name: test object name
        :return: None
        """

        def left_double_click(self, on_element: WebElement = None) -> None:
        """
        double left click mouse on current mouse position or double click on web element
        :param on_element: can be None or web element
        :return: None
        """

        def left_double_click_with_test_object(self, element_name: str = None) -> None:
        """
        double left click mouse on current mouse position or double click on web element
        find use test object name
        :param element_name: test object name
        :return: None
        """

        def release(self, on_element: WebElement = None) -> None:
        """
        release mouse
        :param on_element: can be None or web element
        :return: None
        """

        def release_with_test_object(self, element_name: str = None) -> None:
        """
        release mouse or web element find use test object name
        :param element_name: test object name
        :return: None
        """

        def press_key(self, keycode_on_key_class, on_element: WebElement = None) -> None:
        """
        press key or press key on web element key should be in Key
        :param keycode_on_key_class: which key code to press
        :param on_element: can be None or web element
        :return: None
        """

        def press_key_with_test_object(self, keycode_on_key_class, element_name: str = None) -> None:
        """
        press key or press key on web element key should be in Key find web element use test object name
        :param keycode_on_key_class: which key code to press
        :param element_name: test object name
        :return: None
        """

        def release_key(self, keycode_on_key_class, on_element: WebElement = None) -> None:
        """
        release key or press key on web element key should be in Key
        :param keycode_on_key_class: which key code to release
        :param on_element: can be None or web element
        :return: None
        """

        def release_key_with_test_object(self, keycode_on_key_class, element_name: str = None) -> None:
        """
        release key or release key on web element key should be in Key
        find use test object
        :param keycode_on_key_class: which key code to release
        :param element_name: test object name
        :return: None
        """

        def move_by_offset(self, offset_x: int, offset_y: int) -> None:
        """
        move mouse use offset
        :param offset_x: offset x
        :param offset_y: offset y
        :return: None
        """

        def pause(self, seconds: int) -> None:
        """
        pause seconds time (this many be let selenium raise some exception)
        :param seconds: seconds to pause
        :return: None
        """

        def send_keys(self, keys_to_send) -> None:
        """
        send(press and release) keyboard key
        :param keys_to_send: what key on keyboard we want to send
        :return: None
        """

        def send_keys_to_element(self, element: WebElement, keys_to_send) -> None:
        """
        :param element: which element we want send key to
        :param keys_to_send:  which key on keyboard we want to send
        :return: None
        """

        def send_keys_to_element_with_test_object(self, element_name: str, keys_to_send) -> None:
        """
        :param element_name: test object name
        :param keys_to_send:  which key on keyboard we want to send find use test object
        :return: None
        """

        def scroll(self, scroll_x: int, scroll_y: int, delta_x: int, delta_y: int,
                duration: int = 0, origin: str = "viewport") -> None:
        """
        :param scroll_x: starting x coordinate
        :param scroll_y: starting y coordinate
        :param delta_x: the distance the mouse will scroll on the x axis
        :param delta_y: the distance the mouse will scroll on the y axis
        :param duration: delay to wheel
        :param origin: what is origin to scroll
        :return:
        """

        def maximize_window(self) -> None:
        """
        maximize current window
        :return: None
        """

        def fullscreen_window(self) -> None:
        """
        fullscreen current window
        :return: None
        """

        def minimize_window(self) -> None:
        """
        minimize current window
        :return: None
        """

        def set_window_size(self, width, height, window_handle='current') -> dict:
        """
        :param width: window width (pixel)
        :param height: window height (pixel)
        :param window_handle: normally is "current" (w3c)  if not "current" will make exception
        :return: size
        """

        def set_window_position(self, x, y, window_handle='current') -> dict:
        """
        :param x: position x
        :param y: position y
        :param window_handle: normally is "current" (w3c)  if not "current" will make exception
        :return: execute(Command.SET_WINDOW_RECT,
        {"x": x, "y": y, "width": width, "height": height})['value']
        """

        def get_window_rect(self) -> dict:
        """
        :return: execute(Command.GET_WINDOW_RECT)['value']
        """

        def set_window_rect(self, x=None, y=None, width=None, height=None) -> dict:
        """
        only supported for w3c compatible another browsers need use set_window_position or set_window_size
        :param x: set x coordinates
        :param y: set y coordinates
        :param width: set window width
        :param height: set window height
        :return: execute(Command.SET_WINDOW_RECT,
        {"x": x, "y": y, "width": width, "height": height})['value']
        """

        def get_screenshot_as_png(self) -> bytes:
        """
        get current page screenshot as png
        :return: screenshot as bytes
        """

        def get_screenshot_as_base64(self) -> str:
        """
        get current page screenshot as base64 str
        :return: screenshot as str
        """

        def get_log(self, log_type: str):
        """
        :param log_type: ["browser", "driver", client", "server]
        :return: execute(Command.GET_LOG, {'type': log_type})['value']
        """

        def check_current_webdriver(self, check_dict: dict) -> None:
        """
        if check failure will raise an exception
        :param check_dict: use to check current webdriver state
        :return: None
        """

        def quit(self) -> None:
        """
        quit this webdriver
        :return: None
        """