from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance
from je_web_runner.manager.webrunner_manager import get_webdriver_manager
from je_web_runner.webdriver.webdriver_with_options import set_webdriver_options_argument
from je_web_runner.utils.selenium_utils_wrapper.desired_capabilities.desired_capabilities import \
    get_desired_capabilities_keys, get_desired_capabilities
from je_web_runner.utils.selenium_utils_wrapper.keys.selenium_keys import Keys
from je_web_runner.utils.executor.action_executor import add_command_to_executor
from je_web_runner.utils.executor.action_executor import execute_action
from je_web_runner.utils.executor.action_executor import execute_files
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.file_process.get_dir_file_list import get_dir_files_as_list
from je_web_runner.utils.generate_report.generate_html_report import generate_html
from je_web_runner.utils.generate_report.generate_html_report import generate_html_report
from je_web_runner.utils.generate_report.generate_json_report import generate_json
from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.json.json_validator import validate_action_file
from je_web_runner.utils.json.json_validator import validate_action_files
from je_web_runner.utils.json.json_validator import validate_action_json
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml_report
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
from je_web_runner.utils.socket_server.web_runner_socket_server import start_web_runner_socket_server
from je_web_runner.utils.test_object.test_object_class import TestObject
from je_web_runner.utils.test_object.test_object_class import create_test_object
from je_web_runner.utils.test_object.test_object_class import get_test_object_type_list
from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.utils.callback.callback_function_executor import callback_executor
from je_web_runner.utils.data_driven.data_runner import (
    DataDrivenError,
    expand_with_row,
    load_dataset_csv,
    load_dataset_json,
    run_with_dataset,
)
from je_web_runner.utils.env_config.env_loader import EnvConfigError, expand_in_action, get_env, load_env
from je_web_runner.utils.project.create_project_structure import create_project_dir
from je_web_runner.utils.visual_regression.visual_diff import capture_baseline as visual_capture_baseline
from je_web_runner.utils.visual_regression.visual_diff import compare_with_baseline as visual_compare_with_baseline
from je_web_runner.webdriver.playwright_wrapper import (
    PlaywrightBackendError,
    PlaywrightWrapper,
    playwright_wrapper_instance,
    pw_add_cookies,
    pw_back,
    pw_check,
    pw_clear_cookies,
    pw_click,
    pw_close_page,
    pw_content,
    pw_dblclick,
    pw_drag_and_drop,
    pw_evaluate,
    pw_fill,
    pw_find_element,
    pw_find_element_with_test_object_record,
    pw_find_elements,
    pw_find_elements_with_test_object_record,
    pw_forward,
    pw_get_cookies,
    pw_hover,
    pw_keyboard_down,
    pw_keyboard_press,
    pw_keyboard_type,
    pw_keyboard_up,
    pw_launch,
    pw_start_har_recording,
    pw_stop_har_recording,
    pw_mouse_click,
    pw_mouse_down,
    pw_mouse_move,
    pw_mouse_up,
    pw_new_page,
    pw_page_count,
    pw_press,
    pw_quit,
    pw_refresh,
    pw_save_test_object_to_selector,
    pw_screenshot,
    pw_screenshot_bytes,
    pw_select_option,
    pw_set_default_navigation_timeout,
    pw_set_default_timeout,
    pw_set_viewport_size,
    pw_switch_to_page,
    pw_title,
    pw_to_url,
    pw_type_text,
    pw_uncheck,
    pw_url,
    pw_viewport_size,
    pw_wait_for_load_state,
    pw_wait_for_selector,
    pw_wait_for_timeout,
    pw_wait_for_url,
)
from je_web_runner.webdriver.playwright_element_wrapper import (
    PlaywrightElementWrapper,
    playwright_element_wrapper,
)
from je_web_runner.utils.recorder.browser_recorder import events_to_actions as recorder_events_to_actions
from je_web_runner.utils.recorder.browser_recorder import pull_events as recorder_pull_events
from je_web_runner.utils.recorder.browser_recorder import save_recording as recorder_save_recording
from je_web_runner.utils.recorder.browser_recorder import start_recording as recorder_start
from je_web_runner.utils.recorder.browser_recorder import stop_recording as recorder_stop
__all__ = [
    "web_element_wrapper", "set_webdriver_options_argument",
    "webdriver_wrapper_instance", "get_webdriver_manager",
    "get_desired_capabilities", "get_desired_capabilities_keys", "add_command_to_executor",
    "execute_action", "execute_files", "executor",
    "generate_html", "generate_html_report",
    "generate_json", "generate_json_report", "read_action_json",
    "generate_xml", "generate_xml_report",
    "generate_junit_xml", "generate_junit_xml_report",
    "start_web_runner_socket_server", "get_dir_files_as_list",
    "TestObject", "create_test_object", "get_test_object_type_list",
    "test_record_instance", "Keys", "callback_executor", "create_project_dir",
    "load_env", "get_env", "expand_in_action", "EnvConfigError",
    "load_dataset_csv", "load_dataset_json", "expand_with_row",
    "run_with_dataset", "DataDrivenError",
    "validate_action_json", "validate_action_file", "validate_action_files",
    "visual_capture_baseline", "visual_compare_with_baseline",
    "recorder_start", "recorder_stop", "recorder_pull_events",
    "recorder_events_to_actions", "recorder_save_recording",
    "PlaywrightBackendError", "PlaywrightWrapper", "playwright_wrapper_instance",
    "PlaywrightElementWrapper", "playwright_element_wrapper",
    "pw_launch", "pw_quit", "pw_start_har_recording", "pw_stop_har_recording",
    "pw_to_url", "pw_forward", "pw_back", "pw_refresh",
    "pw_url", "pw_title", "pw_content",
    "pw_set_default_timeout", "pw_set_default_navigation_timeout",
    "pw_new_page", "pw_switch_to_page", "pw_close_page", "pw_page_count",
    "pw_find_element", "pw_find_elements",
    "pw_find_element_with_test_object_record", "pw_find_elements_with_test_object_record",
    "pw_save_test_object_to_selector",
    "pw_click", "pw_dblclick", "pw_hover",
    "pw_fill", "pw_type_text", "pw_press",
    "pw_check", "pw_uncheck", "pw_select_option", "pw_drag_and_drop",
    "pw_evaluate",
    "pw_get_cookies", "pw_add_cookies", "pw_clear_cookies",
    "pw_screenshot", "pw_screenshot_bytes",
    "pw_wait_for_selector", "pw_wait_for_load_state",
    "pw_wait_for_timeout", "pw_wait_for_url",
    "pw_set_viewport_size", "pw_viewport_size",
    "pw_mouse_click", "pw_mouse_move", "pw_mouse_down", "pw_mouse_up",
    "pw_keyboard_press", "pw_keyboard_type", "pw_keyboard_down", "pw_keyboard_up"
]
