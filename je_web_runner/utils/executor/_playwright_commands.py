"""
Playwright backend 的 WR_pw_* 指令 / The ``WR_pw_*`` commands of the Playwright backend.

Part of the command table in :mod:`je_web_runner.utils.executor._event_table`,
kept apart so neither file passes the 750-line limit.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.webdriver import playwright_wrapper as _pw
from je_web_runner.webdriver.playwright_element_wrapper import playwright_element_wrapper as _pw_element

PLAYWRIGHT_COMMANDS: dict[str, Any] = {
    # playwright backend — page-level operations
    "WR_pw_launch": _pw.pw_launch,
    "WR_pw_quit": _pw.pw_quit,
    "WR_pw_start_har_recording": _pw.pw_start_har_recording,
    "WR_pw_stop_har_recording": _pw.pw_stop_har_recording,
    # network route mocking
    "WR_pw_route_mock": _pw.pw_route_mock,
    "WR_pw_route_mock_json": _pw.pw_route_mock_json,
    "WR_pw_route_unmock": _pw.pw_route_unmock,
    "WR_pw_route_clear": _pw.pw_route_clear,
    # device emulation
    "WR_pw_emulate": _pw.pw_emulate,
    "WR_pw_stop_emulate": _pw.pw_stop_emulate,
    "WR_pw_list_devices": _pw.pw_list_devices,
    # geolocation / permissions / timezone / clock
    "WR_pw_set_geolocation": _pw.pw_set_geolocation,
    "WR_pw_grant_permissions": _pw.pw_grant_permissions,
    "WR_pw_clear_permissions": _pw.pw_clear_permissions,
    "WR_pw_set_timezone": _pw.pw_set_timezone,
    "WR_pw_clock_install": _pw.pw_clock_install,
    "WR_pw_clock_set_time": _pw.pw_clock_set_time,
    "WR_pw_clock_run_for": _pw.pw_clock_run_for,
    "WR_pw_set_locale": _pw.pw_set_locale,
    "WR_pw_set_context_options": _pw.pw_set_context_options,
    "WR_pw_set_user_agent": _pw.pw_set_user_agent,
    "WR_pw_set_extra_http_headers": _pw.pw_set_extra_http_headers,
    "WR_pw_save_storage_state": _pw.pw_save_storage_state,
    # trace viewer / video
    "WR_pw_tracing_start": _pw.pw_tracing_start,
    "WR_pw_tracing_save_chunk": _pw.pw_tracing_save_chunk,
    "WR_pw_tracing_stop": _pw.pw_tracing_stop,
    "WR_pw_video_start": _pw.pw_video_start,
    "WR_pw_video_stop": _pw.pw_video_stop,
    # twins of Selenium commands
    "WR_pw_add_init_script": _pw.pw_add_init_script,
    "WR_pw_block_urls": _pw.pw_block_urls,
    "WR_pw_unblock_urls": _pw.pw_unblock_urls,
    "WR_pw_clear_geolocation": _pw.pw_clear_geolocation,
    "WR_pw_bring_to_front": _pw.pw_bring_to_front,
    "WR_pw_switch_to_page_by_url": _pw.pw_switch_to_page_by_url,
    "WR_pw_switch_to_page_by_title": _pw.pw_switch_to_page_by_title,
    "WR_pw_screenshot_base64": _pw.pw_screenshot_base64,
    "WR_pw_print_page": _pw.pw_print_page,
    "WR_pw_scroll": _pw.pw_scroll,
    "WR_pw_scroll_to_top": _pw.pw_scroll_to_top,
    "WR_pw_scroll_to_bottom": _pw.pw_scroll_to_bottom,
    "WR_pw_drag_and_drop_offset": _pw.pw_drag_and_drop_offset,
    "WR_pw_to_url": _pw.pw_to_url,
    "WR_pw_forward": _pw.pw_forward,
    "WR_pw_back": _pw.pw_back,
    "WR_pw_refresh": _pw.pw_refresh,
    "WR_pw_url": _pw.pw_url,
    "WR_pw_title": _pw.pw_title,
    "WR_pw_content": _pw.pw_content,
    "WR_pw_set_default_timeout": _pw.pw_set_default_timeout,
    "WR_pw_set_default_navigation_timeout": _pw.pw_set_default_navigation_timeout,
    # pages / tabs
    "WR_pw_new_page": _pw.pw_new_page,
    "WR_pw_switch_to_page": _pw.pw_switch_to_page,
    "WR_pw_close_page": _pw.pw_close_page,
    "WR_pw_page_count": _pw.pw_page_count,
    # finding
    "WR_pw_find_element": _pw.pw_find_element,
    "WR_pw_find_elements": _pw.pw_find_elements,
    "WR_pw_find_element_with_test_object_record": _pw.pw_find_element_with_test_object_record,
    "WR_pw_find_elements_with_test_object_record": _pw.pw_find_elements_with_test_object_record,
    "WR_pw_save_test_object_to_selector": _pw.pw_save_test_object_to_selector,
    # direct page-level shortcuts
    "WR_pw_click": _pw.pw_click,
    "WR_pw_dblclick": _pw.pw_dblclick,
    "WR_pw_hover": _pw.pw_hover,
    "WR_pw_fill": _pw.pw_fill,
    "WR_pw_type_text": _pw.pw_type_text,
    "WR_pw_press": _pw.pw_press,
    "WR_pw_check": _pw.pw_check,
    "WR_pw_uncheck": _pw.pw_uncheck,
    "WR_pw_select_option": _pw.pw_select_option,
    "WR_pw_drag_and_drop": _pw.pw_drag_and_drop,
    # script
    "WR_pw_evaluate": _pw.pw_evaluate,
    # cookies
    "WR_pw_get_cookies": _pw.pw_get_cookies,
    "WR_pw_add_cookies": _pw.pw_add_cookies,
    "WR_pw_clear_cookies": _pw.pw_clear_cookies,
    # screenshots
    "WR_pw_screenshot": _pw.pw_screenshot,
    "WR_pw_screenshot_bytes": _pw.pw_screenshot_bytes,
    # waits
    "WR_pw_wait_for_selector": _pw.pw_wait_for_selector,
    "WR_pw_wait_for_load_state": _pw.pw_wait_for_load_state,
    "WR_pw_wait_for_timeout": _pw.pw_wait_for_timeout,
    "WR_pw_wait_for_url": _pw.pw_wait_for_url,
    # viewport
    "WR_pw_set_viewport_size": _pw.pw_set_viewport_size,
    "WR_pw_viewport_size": _pw.pw_viewport_size,
    # mouse / keyboard
    "WR_pw_mouse_click": _pw.pw_mouse_click,
    "WR_pw_mouse_move": _pw.pw_mouse_move,
    "WR_pw_mouse_down": _pw.pw_mouse_down,
    "WR_pw_mouse_up": _pw.pw_mouse_up,
    "WR_pw_keyboard_press": _pw.pw_keyboard_press,
    "WR_pw_keyboard_type": _pw.pw_keyboard_type,
    "WR_pw_keyboard_down": _pw.pw_keyboard_down,
    "WR_pw_keyboard_up": _pw.pw_keyboard_up,
    # element-level (operates on captured current element)
    "WR_pw_element_click": _pw_element.click,
    "WR_pw_element_dblclick": _pw_element.dblclick,
    "WR_pw_element_hover": _pw_element.hover,
    "WR_pw_element_fill": _pw_element.fill,
    "WR_pw_element_type_text": _pw_element.type_text,
    "WR_pw_element_press": _pw_element.press,
    "WR_pw_element_clear": _pw_element.clear,
    "WR_pw_element_check": _pw_element.check,
    "WR_pw_element_uncheck": _pw_element.uncheck,
    "WR_pw_element_select_option": _pw_element.select_option,
    "WR_pw_element_get_attribute": _pw_element.get_attribute,
    "WR_pw_element_get_property": _pw_element.get_property,
    "WR_pw_element_inner_text": _pw_element.inner_text,
    "WR_pw_element_inner_html": _pw_element.inner_html,
    "WR_pw_element_is_visible": _pw_element.is_visible,
    "WR_pw_element_is_enabled": _pw_element.is_enabled,
    "WR_pw_element_is_checked": _pw_element.is_checked,
    "WR_pw_element_scroll_into_view": _pw_element.scroll_into_view,
    "WR_pw_element_screenshot": _pw_element.screenshot,
    "WR_pw_element_change": _pw_element.change_element,
}
