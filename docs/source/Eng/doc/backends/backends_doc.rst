========
Backends
========

Selenium (default)
==================

The original ``WebDriverWrapper`` plus ``WebElementWrapper``. All commands
without a more specific prefix dispatch here.

Playwright
==========

The Playwright backend lives under ``WR_pw_*`` and is opt-in: existing
scripts keep running on Selenium. It covers most everyday operations, but it
is not a one-to-one copy of the Selenium surface. The tables below list the
equivalent commands and how they differ, then what exists on one backend only.

* Lifecycle / pages / navigation. Pages the site opens itself (popups,
  ``window.open``) are tracked, so ``WR_pw_switch_to_page`` can reach them.
* Find (with ``TestObject`` translation) and direct page-level shortcuts. The
  shortcuts pass extra Playwright options through (``button``,
  ``modifiers``, ``timeout``, ``force``, ``wait_until`` …).
* Element-level wrapper
* Mobile emulation, locale, timezone, geolocation, permissions, clock
* HAR recording, route mocking, console + network event capture
* Network throttling presets via CDP

Page-level actions are added to the test record, so they appear in the
generated reports like Selenium steps.

Equivalent commands
-------------------

.. list-table::
   :header-rows: 1
   :widths: 16 30 30 24

   * - Task
     - Selenium
     - Playwright
     - Difference
   * - Start / stop
     - ``WR_get_webdriver_manager`` (``WR_new_driver``), ``WR_quit``
     - ``WR_pw_launch``, ``WR_pw_quit``
     - Playwright runs Chromium, Firefox or WebKit, one browser and one
       context at a time.
   * - Attach, profile, remote
     - ``WR_attach_to_existing_browser``, ``WR_chrome_options_with_extension``,
       ``WR_start_remote_driver``
     - ``WR_pw_connect_over_cdp``, ``WR_pw_launch_persistent``
       (``extension_paths``), ``WR_pw_connect`` (a Playwright browser server)
     - An attached or persistent Playwright context keeps its options: the
       settings that rebuild a context raise there. Quitting an attached
       browser only disconnects.
   * - Navigate
     - ``WR_to_url``, ``WR_back``, ``WR_forward``, ``WR_refresh``
     - ``WR_pw_to_url``, ``WR_pw_back``, ``WR_pw_forward``, ``WR_pw_refresh``
     - ``WR_pw_to_url`` accepts ``goto`` options such as ``wait_until``.
   * - Page info
     - ``WR_get_current_url``, ``WR_get_title``, ``WR_get_page_source``
     - ``WR_pw_url``, ``WR_pw_title``, ``WR_pw_content``
     - Names only.
   * - Find a recorded ``TestObject``
     - ``WR_find_recorded_element``, ``WR_find_recorded_elements``
     - ``WR_pw_find_element_with_test_object_record``,
       ``WR_pw_find_elements_with_test_object_record``
     - The ``TestObject`` is translated to a Playwright selector.
   * - Click, hover
     - ``WR_element_click``; ``WR_left_click`` / ``WR_move_to_element``
       then ``WR_perform``
     - ``WR_pw_element_click`` / ``WR_pw_element_hover``, or ``WR_pw_click``
       / ``WR_pw_hover`` with a selector
     - Selenium's ActionChains commands queue until ``WR_perform``;
       Playwright acts at once.
   * - Type
     - ``WR_element_input``
     - ``WR_pw_element_type_text``, ``WR_pw_element_fill``
     - ``WR_element_input`` and ``type_text`` append; ``fill`` replaces the
       value.
   * - Select an option
     - ``WR_element_select_by_value`` / ``_by_index`` / ``_by_visible_text``
     - ``WR_pw_select_option``, ``WR_pw_element_select_option``
     - Playwright takes a value, ``{"index": n}`` or ``{"label": text}``.
   * - Wait
     - ``WR_implicitly_wait``
     - ``WR_pw_wait_for_selector`` / ``_url`` / ``_load_state`` /
       ``_timeout``
     - Playwright also waits for an element to be actionable before every
       action.
   * - Timeouts
     - ``WR_set_page_load_timeout``, ``WR_set_script_timeout``
     - ``WR_pw_set_default_timeout``,
       ``WR_pw_set_default_navigation_timeout``
     - Seconds on Selenium, milliseconds on Playwright.
   * - JavaScript
     - ``WR_execute_script``, ``WR_execute_async_script``
     - ``WR_pw_evaluate``
     - ``WR_set_allow_arbitrary_script(False)`` closes both.
   * - Screenshot
     - ``WR_save_screenshot``, ``WR_save_full_page_screenshot``,
       ``WR_get_screenshot_as_png``, ``WR_get_screenshot_as_base64``
     - ``WR_pw_screenshot`` (``full_page``), ``WR_pw_screenshot_bytes``,
       ``WR_pw_screenshot_base64``
     - Same forms on both.
   * - PDF
     - ``WR_print_page``
     - ``WR_pw_print_page``
     - Playwright prints only from headless Chromium.
   * - Cookies
     - ``WR_get_cookies``, ``WR_get_cookie``, ``WR_add_cookie``,
       ``WR_delete_cookie``, ``WR_delete_all_cookies``, ``WR_save_cookies``,
       ``WR_load_cookies``
     - ``WR_pw_get_cookies``, ``WR_pw_get_cookie``, ``WR_pw_add_cookies``
       (a list), ``WR_pw_delete_cookie``, ``WR_pw_clear_cookies``,
       ``WR_pw_save_storage_state`` (load it back with the ``storage_state``
       context option)
     - Playwright's saved state holds cookies and localStorage together.
   * - Submit, CSS value, DOM attribute
     - ``WR_element_submit``, ``WR_element_value_of_css_property``,
       ``WR_element_get_dom_attribute``
     - ``WR_pw_element_submit``, ``WR_pw_element_value_of_css_property``,
       ``WR_pw_element_get_attribute``
     - Playwright's ``get_attribute`` already reads the DOM attribute.
       ``WR_pw_element_submit`` uses the form's ``requestSubmit``, so its
       submit event and validation run.
   * - Assertions
     - ``WR_check_current_webdriver``, ``WR_element_assert``
     - ``WR_pw_check_current_page`` (``title``, ``url`` / ``current_url``,
       ``viewport_size``, ``page_count``), ``WR_pw_element_assert``
       (``tag_name``, ``text``, ``value``, ``visible``, ``enabled``,
       ``checked``, ``size``, ``location``)
     - The Playwright checks raise, so a mismatch fails its action. The
       Selenium ones record the mismatch in the test record but let the
       action pass.
   * - Tabs
     - ``WR_new_window``, ``WR_switch``, ``WR_switch_to_window_by_url``,
       ``WR_switch_to_window_by_title``, ``WR_close_window``
     - ``WR_pw_new_page``, ``WR_pw_switch_to_page`` (by index),
       ``WR_pw_switch_to_page_by_url``, ``WR_pw_switch_to_page_by_title``,
       ``WR_pw_close_page``, ``WR_pw_page_count``, ``WR_pw_bring_to_front``
     - URL and title match a case-sensitive substring on both; Playwright also
       tracks pages the site opens itself.
   * - Scroll, drag by an offset
     - ``WR_scroll``, ``WR_scroll_to_top``, ``WR_scroll_to_bottom``,
       ``WR_drag_and_drop_offset``
     - ``WR_pw_scroll``, ``WR_pw_scroll_to_top``, ``WR_pw_scroll_to_bottom``,
       ``WR_pw_drag_and_drop_offset``
     - Playwright's drag takes a selector; Selenium's drags the element
       passed to it.
   * - Init script, blocked URLs
     - ``WR_add_script_to_evaluate_on_new_document``, ``WR_block_urls`` /
       ``WR_unblock_urls`` (CDP)
     - ``WR_pw_add_init_script``, ``WR_pw_block_urls`` / ``WR_pw_unblock_urls``
     - Selenium's are Chromium-only. Patterns use ``*`` for anything on both.
       On Playwright both carry over to rebuilt contexts; both init-script
       commands are behind the arbitrary-script gate.
   * - Frames
     - ``WR_switch``, ``WR_iframe_switch_chain``,
       ``WR_iframe_back_to_default``
     - ``WR_pw_switch_to_frame`` (a selector or a list for nested iframes),
       ``WR_pw_switch_to_parent_frame``, ``WR_pw_switch_to_main_frame``
     - The same model on both: the selector commands act in the selected
       frame until you switch back; on Playwright a navigation or a page
       switch also returns to the page. Mouse, keyboard and screenshots stay
       page-level.
   * - Device emulation
     - ``WR_set_device_metrics`` + ``WR_set_user_agent``
     - ``WR_pw_emulate``, ``WR_pw_list_devices``
     - Selenium's form is Chromium-only (CDP) and has no named devices.
   * - Geolocation, timezone, locale
     - ``WR_set_geolocation``, ``WR_set_timezone``, ``WR_set_locale``
     - ``WR_pw_set_geolocation``, ``WR_pw_set_timezone``,
       ``WR_pw_set_locale``
     - ``WR_pw_clear_geolocation`` clears the override (Selenium:
       ``WR_clear_geolocation_override``). Selenium's are Chromium-only (CDP). ``WR_pw_set_timezone`` and
       ``WR_pw_set_locale`` rebuild the Playwright context: cookies,
       localStorage and the current page's URL carry over, other open pages
       close.
   * - User agent, extra headers, other context options
     - ``WR_set_user_agent``, ``WR_set_extra_http_headers`` (CDP)
     - ``WR_pw_set_user_agent``, ``WR_pw_set_extra_http_headers``,
       ``WR_pw_set_context_options`` (any ``browser.new_context`` option),
       ``WR_pw_launch`` with ``context_options``
     - Selenium's are Chromium-only. Playwright keeps one merged set of
       context options, so each setting leaves the others in place.
   * - Downloads, cache
     - ``WR_set_download_directory`` + ``WR_wait_for_download``,
       ``WR_set_cache_disabled`` (CDP)
     - ``WR_pw_download(selector, save_to)`` (clicks and saves in one step),
       ``WR_pw_set_cache_disabled``
     - Playwright's cache switch works on every browser: any active route
       turns the HTTP cache off.
   * - Visual regression, recorder, callbacks
     - ``WR_visual_capture_baseline``, ``WR_visual_compare``,
       ``WR_recorder_start`` / ``_stop`` / ``_pull_events`` / ``_save``; the
       callback executor
     - ``WR_pw_visual_capture_baseline``, ``WR_pw_visual_compare``,
       ``WR_pw_recorder_start`` / ``_stop`` / ``_pull_events`` / ``_save``;
       every ``WR_pw_*`` command is also a callback trigger
     - Same behaviour: the same comparison and recorder script run on the
       Playwright page.
   * - Throttling, raw CDP
     - ``WR_throttle``, ``WR_set_network_conditions``,
       ``WR_execute_cdp_cmd``, ``WR_cdp``
     - ``WR_pw_throttle``, ``WR_pw_cdp``
     - Chromium only on both.
   * - Storage, service workers, shadow DOM, upload, self-healing, axe,
       performance
     - ``WR_local_storage_*``, ``WR_session_storage_*``, ``WR_sw_*``,
       ``WR_shadow_query``, ``WR_upload_file``, ``WR_find_with_healing``,
       ``WR_a11y_run_audit``, ``WR_perf_collect``
     - The same names with ``WR_pw_`` in front (``WR_pw_shadow_query``,
       ``WR_pw_a11y_run_audit`` …)
     - Same behaviour.

Only on Selenium
----------------

Not possible on Playwright:

* Internet Explorer and the real Safari browser; Playwright's WebKit is not
  Safari.
* Selenium Grid and the cloud grids (``WR_start_remote_driver``,
  ``WR_connect_browserstack`` …): they speak the WebDriver protocol, which
  Playwright does not.
* Appium mobile sessions (``WR_appium_*``).
* Window geometry (``WR_maximize_window``, ``WR_minimize_window``,
  ``WR_fullscreen_window``, ``WR_set_window_position``,
  ``WR_set_window_rect``): Playwright controls the viewport, not the OS
  window. ``WR_pw_set_viewport_size`` is the nearest equivalent.

Not on Playwright yet (the Playwright API supports them):

* several drivers at once (``WR_new_driver`` more than once,
  ``WR_change_index_of_webdriver``).

Only on Playwright
------------------

Not possible on Selenium:

* WebKit.
* The trace viewer and native video recording (``WR_pw_tracing_start`` /
  ``WR_pw_tracing_stop``, ``WR_pw_video_start`` / ``WR_pw_video_stop``).
* Waiting for actionability before every action; Selenium only has implicit
  and explicit waits.

Not on Selenium yet:

* ``WR_pw_check``, ``WR_pw_uncheck``, ``WR_pw_element_is_checked``,
  ``WR_pw_element_inner_text``, ``WR_pw_element_inner_html``, and finding
  by a raw selector (``WR_pw_find_element``);
* ``WR_pw_route_mock`` / ``WR_pw_route_mock_json``. Selenium has the CDP
  Fetch primitives (``WR_enable_fetch_interception`` …), but an action file
  cannot complete them because it never learns the paused request's id;
* ``WR_pw_start_har_recording``, ``WR_pw_event_capture_start``,
  ``WR_pw_assert_no_console_errors``;
* ``WR_pw_grant_permissions``, ``WR_pw_clock_install``, and named devices
  (``WR_pw_emulate``);
* answering JavaScript dialogs: ``WR_pw_set_dialog_policy`` (``accept`` with
  an optional prompt text, ``dismiss``) and ``WR_pw_last_dialog``. Selenium
  reaches an alert through ``WR_switch`` but has no accept or dismiss
  command.

Only approximated on Selenium: finding elements the way a user would,
``WR_pw_find_by`` (``role``, ``text``, ``label``, ``placeholder``,
``alt_text``, ``title``, ``test_id``). Selenium can only express these as
XPath.

Cloud Grid
==========

Provider helpers for BrowserStack, Sauce Labs, and LambdaTest:

* ``connect_browserstack`` / ``connect_saucelabs`` / ``connect_lambdatest``
* ``build_browserstack_capabilities`` / ``build_saucelabs_capabilities`` /
  ``build_lambdatest_capabilities``
* ``start_remote_driver`` for arbitrary hub URLs

Appium (mobile)
===============

``start_appium_session`` builds an Appium WebDriver and registers it on the
shared Selenium wrapper so existing ``WR_*`` commands keep working against a
mobile session. Capability builders cover both Android (UiAutomator2) and
iOS (XCUITest).

``appium_integration.gestures`` adds higher-level mobile gestures —
``swipe`` / ``scroll`` / ``long_press`` / ``pinch`` / ``double_tap``
prefer Appium's ``mobile:`` named extensions and fall back to W3C Actions
sequences.
