WebDriver Wrapper
=================

Overview
--------

``WebDriverWrapper`` is the central component that wraps Selenium WebDriver with comprehensive methods.
It provides a unified interface for browser control, element finding, mouse/keyboard actions,
cookie management, JavaScript execution, window management, and more.

The global instance ``webdriver_wrapper_instance`` is used internally by the manager and executor.

Navigation
----------

.. code-block:: python

    wrapper = manager.webdriver_wrapper

    wrapper.to_url("https://example.com")    # Navigate to URL
    wrapper.forward()                        # Go forward
    wrapper.back()                           # Go back
    wrapper.refresh()                        # Refresh the page

Element Finding
---------------

Find elements using ``TestObject`` locators:

.. code-block:: python

    from je_web_runner import TestObject

    # Locator strategies: id, name, xpath, css selector,
    # class name, tag name, link text, partial link text
    element = TestObject("search-input", "id")

    wrapper.find_element(element)       # Find single element
    wrapper.find_elements(element)      # Find multiple elements

Find elements using saved ``TestObjectRecord`` names:

.. code-block:: python

    # Using saved test objects (stored by name in TestObjectRecord)
    wrapper.find_element_with_test_object_record("search-input")
    wrapper.find_elements_with_test_object_record("search-input")

Wait Methods
------------

.. code-block:: python

    wrapper.implicitly_wait(5)           # Implicit wait (seconds)
    wrapper.explict_wait(                # Explicit WebDriverWait
        wait_condition,
        timeout=10,
        poll_frequency=0.5
    )
    wrapper.set_script_timeout(30)       # Async script timeout
    wrapper.set_page_load_timeout(60)    # Page load timeout

Mouse Actions
-------------

**Basic clicks (at current position):**

.. code-block:: python

    wrapper.left_click()
    wrapper.right_click()
    wrapper.left_double_click()
    wrapper.left_click_and_hold()
    wrapper.release()

**Clicks on saved test objects:**

.. code-block:: python

    wrapper.left_click_with_test_object("button_name")
    wrapper.right_click_with_test_object("button_name")
    wrapper.left_double_click_with_test_object("button_name")
    wrapper.left_click_and_hold_with_test_object("button_name")
    wrapper.release_with_test_object("button_name")

**Drag and drop:**

.. code-block:: python

    wrapper.drag_and_drop(source_element, target_element)
    wrapper.drag_and_drop_offset(element, x=100, y=50)

    # Using saved test objects
    wrapper.drag_and_drop_with_test_object("source_name", "target_name")
    wrapper.drag_and_drop_offset_with_test_object("element_name", offset_x=100, offset_y=50)

**Mouse movement:**

.. code-block:: python

    wrapper.move_to_element(element)             # Hover over element
    wrapper.move_to_element_with_test_object("element_name")
    wrapper.move_to_element_with_offset(element, offset_x=10, offset_y=10)
    wrapper.move_to_element_with_offset_and_test_object("name", offset_x=10, offset_y=10)
    wrapper.move_by_offset(100, 200)             # Move from current position

Keyboard Actions
----------------

.. code-block:: python

    wrapper.press_key(keycode)
    wrapper.press_key_with_test_object(keycode)
    wrapper.release_key(keycode)
    wrapper.release_key_with_test_object(keycode)
    wrapper.send_keys("text")
    wrapper.send_keys_to_element(element, "text")
    wrapper.send_keys_to_element_with_test_object("element_name", "text")

Action Chain Control
--------------------

.. code-block:: python

    wrapper.perform()          # Execute queued actions
    wrapper.reset_actions()    # Clear action queue
    wrapper.pause(2)           # Pause in action chain (seconds)
    wrapper.scroll(0, 500)     # Scroll page by offset

Cookie Management
-----------------

.. code-block:: python

    wrapper.get_cookies()                              # Get all cookies
    wrapper.get_cookie("session_id")                   # Get specific cookie
    wrapper.add_cookie({"name": "key", "value": "val"})
    wrapper.delete_cookie("session_id")
    wrapper.delete_all_cookies()

JavaScript Execution
--------------------

.. code-block:: python

    wrapper.execute("document.title")
    wrapper.execute_script("return document.title")
    wrapper.execute_async_script("arguments[0]('done')", callback)

Window Management
-----------------

.. code-block:: python

    wrapper.maximize_window()
    wrapper.minimize_window()
    wrapper.fullscreen_window()
    wrapper.set_window_size(1920, 1080)
    wrapper.set_window_position(0, 0)
    wrapper.get_window_position()       # Returns dict
    wrapper.get_window_rect()           # Returns dict
    wrapper.set_window_rect(x=0, y=0, width=1920, height=1080)

Screenshots
-----------

.. code-block:: python

    wrapper.get_screenshot_as_png()       # Returns bytes
    wrapper.get_screenshot_as_base64()    # Returns base64 string

Frame / Window / Alert Switching
--------------------------------

The ``switch()`` method supports the following context types:

.. code-block:: python

    wrapper.switch("frame", "frame_name")
    wrapper.switch("window", "window_handle")
    wrapper.switch("default_content")
    wrapper.switch("parent_frame")
    wrapper.switch("active_element")
    wrapper.switch("alert")

Browser Logs
------------

.. code-block:: python

    wrapper.get_log("browser")

WebDriver Validation
--------------------

.. code-block:: python

    wrapper.check_current_webdriver({"name": "chrome"})
