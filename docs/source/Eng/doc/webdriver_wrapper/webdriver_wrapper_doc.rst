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

Advanced Launch Options
-----------------------

``set_driver`` accepts three optional parameters beyond CLI args:

.. code-block:: python

    wrapper.set_driver(
        "chrome",
        options=["--disable-blink-features=AutomationControlled"],
        experimental_options={                           # Chromium-only
            "excludeSwitches": ["enable-automation"],
            "useAutomationExtension": False,
            "prefs": {"download.default_directory": "/tmp"},
        },
        extension_paths=["/path/to/extension.crx"],      # add_extension
        enable_bidi=True,                                # webSocketUrl capability
    )

Attaching to an already-running browser started with
``--remote-debugging-port=9222``:

.. code-block:: python

    wrapper.attach_to_existing_browser("127.0.0.1:9222")

Page / Window Metadata
----------------------

.. code-block:: python

    wrapper.get_current_url()              # → str
    wrapper.get_title()
    wrapper.get_page_source()
    wrapper.get_window_handles()           # → list[str]
    wrapper.get_current_window_handle()
    wrapper.new_window("tab")              # or "window"
    wrapper.close_window()                 # closes current tab; quit() ends driver

Substring-based tab switching (restores original tab on no match):

.. code-block:: python

    wrapper.switch_to_window_by_url("checkout")
    wrapper.switch_to_window_by_title("Order")

Page Reload / Scroll / Foreground
---------------------------------

.. code-block:: python

    wrapper.reload(ignore_cache=False)     # ignore_cache=True → CDP Page.reload (Ctrl+Shift+R)
    wrapper.scroll_to_element(element)     # JS scrollIntoView({block:'center'})
    wrapper.scroll_to_top(); wrapper.scroll_to_bottom()
    wrapper.bring_to_front()               # CDP Page.bringToFront

Screenshots & PDF
-----------------

.. code-block:: python

    wrapper.save_screenshot("./shot.png")              # → bool
    wrapper.save_full_page_screenshot("./full.png")    # CDP captureBeyondViewport
    wrapper.print_page("./page.pdf")                   # Selenium 4 print_page
    wrapper.get_screenshot_as_png()                    # → bytes (existing)
    wrapper.get_screenshot_as_base64()                 # → str (existing)

Session Persistence
-------------------

.. code-block:: python

    wrapper.to_url("https://example.com/")
    # … log in …
    wrapper.save_cookies("./cookies.json")             # → bool

    # later, after restart:
    wrapper.to_url("https://example.com/")
    added = wrapper.load_cookies("./cookies.json")     # → int (count applied)

    wrapper.clear_origin_storage("https://example.com")  # cookies + localStorage + IDB + cache

CDP Shortcuts (Chromium only)
-----------------------------

Direct command:

.. code-block:: python

    wrapper.execute_cdp_cmd("Page.bringToFront")
    wrapper.execute_cdp_cmd("Page.captureScreenshot", {"format": "png"})

Stealth / fingerprint overrides:

.. code-block:: python

    wrapper.add_script_to_evaluate_on_new_document(
        "Object.defineProperty(navigator, 'webdriver', {get:()=>undefined});"
    )
    wrapper.set_user_agent("Mozilla/5.0 (custom)")
    wrapper.set_extra_http_headers({"X-Run": "ci-123"})
    wrapper.set_geolocation(35.68, 139.69, accuracy=50)
    wrapper.clear_geolocation_override()

Emulation:

.. code-block:: python

    wrapper.set_timezone("Asia/Tokyo")
    wrapper.set_locale("ja-JP")
    wrapper.set_device_metrics(390, 844, device_scale_factor=3, mobile=True)
    wrapper.clear_device_metrics()

Network:

.. code-block:: python

    wrapper.set_network_conditions(
        offline=False, latency=200,
        download_throughput=50_000, upload_throughput=10_000,
    )
    wrapper.block_urls(["*.doubleclick.net/*", "*.googletagmanager.com/*"])
    wrapper.unblock_urls()
    wrapper.set_cache_disabled(True)

Downloads (required for headless):

.. code-block:: python

    wrapper.set_download_directory("./downloads")

CDP Fetch Interception
----------------------

Thin wrappers around ``Fetch.*`` CDP commands. To receive
``Fetch.requestPaused`` events you must subscribe via ``CDPEventListener``
(or Selenium's trio-based devtools listener) on your own:

.. code-block:: python

    wrapper.enable_fetch_interception(patterns=["*/api/*"])
    # In your event handler:
    wrapper.continue_request(req_id, url=rewritten_url, method="POST",
                              post_data="...", headers={"X-Test": "1"})
    wrapper.fulfill_request(req_id, response_code=200,
                             body=b'{"ok": true}',
                             response_headers={"Content-Type": "application/json"})
    wrapper.fail_request(req_id, error_reason="AccessDenied")
    wrapper.disable_fetch_interception()

W3C BiDi Event Listeners
------------------------

Selenium 4.16+ required; launch with ``enable_bidi=True``:

.. code-block:: python

    wrapper.set_driver("chrome", enable_bidi=True)

    sub = wrapper.add_console_listener(lambda entry: print(entry.text))
    err = wrapper.add_js_error_listener(lambda e: print("exception:", e))
    wrapper.remove_console_listener(sub)
    wrapper.remove_js_error_listener(err)

A ``WebRunnerException`` with a clear instruction is raised when BiDi is
unavailable.

Standalone CDP / BiDi Modules
-----------------------------

``CDPEventListener`` (in ``je_web_runner.utils.cdp.event_loop``) opens a
background CDP WebSocket so commands and events share one target session:

.. code-block:: python

    from je_web_runner import CDPEventListener

    with CDPEventListener.from_driver(driver) as listener:
        listener.on("Fetch.requestPaused", on_paused)
        listener.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})
        # …drive the browser…

Requires ``pip install websocket-client``; raises ``CDPEventLoopError`` if missing.

Performance tracing:

.. code-block:: python

    from je_web_runner import record_trace

    record_trace(
        driver, "perf.json",
        categories=["devtools.timeline", "loading"],
        duration=10.0,
    )
    # Open perf.json in chrome://tracing or DevTools "Performance".

Cross-browser BiDi network (Chrome / Edge / Firefox):

.. code-block:: python

    from je_web_runner import (
        bidi_add_request_handler,
        bidi_add_response_handler,
        bidi_add_auth_handler,
        bidi_clear_network_handlers,
    )

    sub = bidi_add_request_handler(driver, lambda req: print(req.url))
    bidi_clear_network_handlers(driver)

Action JSON Aliases
-------------------

Every method above is also reachable from action JSON via a ``WR_*`` alias —
e.g. ``WR_set_timezone``, ``WR_save_cookies``, ``WR_enable_fetch_interception``,
``WR_save_full_page_screenshot``, ``WR_attach_to_existing_browser`` — so the
MCP server's ``webrunner_run_actions`` tool drives them too.

Internal Mixin Layout
---------------------

``WebDriverWrapper`` is composed via mixins under
``je_web_runner/webdriver/_wrapper_mixins/`` to keep each file under the
750-line project limit:

* ``_scripting_mixin.py`` — ``execute``, ``execute_script``,
  ``execute_async_script``, ``execute_cdp_cmd``, all CDP shortcuts, Fetch
  primitives, BiDi listeners
* ``_navigation_mixin.py`` — navigation, scroll, ``switch``, window/tab
  management, window geometry
* ``_cookie_mixin.py`` — cookies + ``save_cookies`` / ``load_cookies`` /
  ``clear_origin_storage``
* ``_actions_mixin.py`` — ActionChains
* ``_media_mixin.py`` — screenshots, ``print_page``, ``get_log``

The composed class, lifecycle (``set_driver``, ``attach_to_existing_browser``,
``quit``), element finding, and waits stay in ``webdriver_wrapper.py``.
Public imports (``webdriver_wrapper_instance``, ``WebDriverWrapper``) are
unchanged.
