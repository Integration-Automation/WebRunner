import builtins
import types
from inspect import getmembers, isbuiltin
from typing import Union

# 禁止暴露於 JSON 動作執行器的內建函式，避免任意程式碼執行
# Builtins that must never be callable from user-supplied JSON actions,
# per CLAUDE.md: "Action executor must only call registered commands;
# never use eval()/exec() on user input."
_UNSAFE_BUILTINS = frozenset({
    "eval", "exec", "compile", "__import__", "__build_class__",
    "open", "input", "breakpoint",
    "globals", "locals", "vars",
    "getattr", "setattr", "delattr",
})

from je_web_runner.manager.webrunner_manager import web_runner
from je_web_runner.utils.exception.exception_tags import add_command_exception_tag
from je_web_runner.utils.exception.exception_tags import executor_data_error, executor_list_error
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException, WebRunnerAddCommandException
from je_web_runner.utils.generate_report.generate_html_report import generate_html
from je_web_runner.utils.generate_report.generate_html_report import generate_html_report
from je_web_runner.utils.generate_report.generate_json_report import generate_json
from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml_report
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.env_config.env_loader import expand_in_action, get_env, load_env
from je_web_runner.utils.json.json_validator import validate_action_file, validate_action_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.package_manager.package_manager_class import package_manager
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.visual_regression.visual_diff import capture_baseline as _visual_capture_baseline
from je_web_runner.utils.visual_regression.visual_diff import compare_with_baseline as _visual_compare
from je_web_runner.webdriver import playwright_wrapper as _pw
from je_web_runner.webdriver.playwright_element_wrapper import playwright_element_wrapper as _pw_element
from je_web_runner.utils.recorder.browser_recorder import pull_events as _recorder_pull_events
from je_web_runner.utils.recorder.browser_recorder import save_recording as _recorder_save_recording
from je_web_runner.utils.recorder.browser_recorder import start_recording as _recorder_start
from je_web_runner.utils.recorder.browser_recorder import stop_recording as _recorder_stop
from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class Executor(object):

    def __init__(self):
        # 事件字典：將字串名稱對應到實際可執行的函式
        # Event dictionary: map string keys to actual callable functions
        self.event_dict = {
            # webdriver manager
            "WR_get_webdriver_manager": web_runner.new_driver,
            "WR_change_index_of_webdriver": web_runner.change_webdriver,
            "WR_quit": web_runner.quit,

            # test object
            "WR_SaveTestObject": test_object_record.save_test_object,
            "WR_CleanTestObject": test_object_record.clean_record,

            # webdriver wrapper
            "WR_set_driver": webdriver_wrapper_instance.set_driver,
            "WR_set_webdriver_options_capability": webdriver_wrapper_instance.set_webdriver_options_capability,
            "WR_find_element": webdriver_wrapper_instance.find_element_with_test_object_record,
            "WR_find_elements": webdriver_wrapper_instance.find_elements_with_test_object_record,
            "WR_implicitly_wait": webdriver_wrapper_instance.implicitly_wait,
            "WR_explict_wait": webdriver_wrapper_instance.explict_wait,
            "WR_to_url": webdriver_wrapper_instance.to_url,
            "WR_forward": webdriver_wrapper_instance.forward,
            "WR_back": webdriver_wrapper_instance.back,
            "WR_refresh": webdriver_wrapper_instance.refresh,
            "WR_switch": webdriver_wrapper_instance.switch,
            "WR_set_script_timeout": webdriver_wrapper_instance.set_script_timeout,
            "WR_set_page_load_timeout": webdriver_wrapper_instance.set_page_load_timeout,
            "WR_get_cookies": webdriver_wrapper_instance.get_cookies,
            "WR_get_cookie": webdriver_wrapper_instance.get_cookie,
            "WR_add_cookie": webdriver_wrapper_instance.add_cookie,
            "WR_delete_cookie": webdriver_wrapper_instance.delete_cookie,
            "WR_delete_all_cookies": webdriver_wrapper_instance.delete_all_cookies,
            "WR_execute": webdriver_wrapper_instance.execute,
            "WR_execute_script": webdriver_wrapper_instance.execute_script,
            "WR_execute_async_script": webdriver_wrapper_instance.execute_async_script,
            "WR_move_to_element": webdriver_wrapper_instance.move_to_element_with_test_object,
            "WR_move_to_element_with_offset": webdriver_wrapper_instance.move_to_element_with_offset_and_test_object,
            "WR_drag_and_drop": webdriver_wrapper_instance.drag_and_drop_with_test_object,
            "WR_drag_and_drop_offset": webdriver_wrapper_instance.drag_and_drop_offset_with_test_object,
            "WR_perform": webdriver_wrapper_instance.perform,
            "WR_reset_actions": webdriver_wrapper_instance.reset_actions,
            "WR_left_click": webdriver_wrapper_instance.left_click_with_test_object,
            "WR_left_click_and_hold": webdriver_wrapper_instance.left_click_and_hold_with_test_object,
            "WR_right_click": webdriver_wrapper_instance.right_click_with_test_object,
            "WR_left_double_click": webdriver_wrapper_instance.left_double_click_with_test_object,
            "WR_release": webdriver_wrapper_instance.release_with_test_object,
            "WR_press_key": webdriver_wrapper_instance.press_key_with_test_object,
            "WR_release_key": webdriver_wrapper_instance.release_key_with_test_object,
            "WR_move_by_offset": webdriver_wrapper_instance.move_by_offset,
            "WR_pause": webdriver_wrapper_instance.pause,
            "WR_send_keys": webdriver_wrapper_instance.send_keys,
            "WR_send_keys_to_element": webdriver_wrapper_instance.send_keys_to_element_with_test_object,
            "WR_scroll": webdriver_wrapper_instance.scroll,
            "WR_check_current_webdriver": webdriver_wrapper_instance.check_current_webdriver,
            "WR_maximize_window": webdriver_wrapper_instance.maximize_window,
            "WR_fullscreen_window": webdriver_wrapper_instance.fullscreen_window,
            "WR_minimize_window": webdriver_wrapper_instance.minimize_window,
            "WR_set_window_size": webdriver_wrapper_instance.set_window_size,
            "WR_set_window_position": webdriver_wrapper_instance.set_window_position,
            "WR_get_window_position": webdriver_wrapper_instance.get_window_position,
            "WR_get_window_rect": webdriver_wrapper_instance.get_window_rect,
            "WR_set_window_rect": webdriver_wrapper_instance.set_window_rect,
            "WR_get_screenshot_as_png": webdriver_wrapper_instance.get_screenshot_as_png,
            "WR_get_screenshot_as_base64": webdriver_wrapper_instance.get_screenshot_as_base64,
            "WR_get_log": webdriver_wrapper_instance.get_log,
            "WR_single_quit": webdriver_wrapper_instance.quit,

            # web element
            "WR_element_submit": web_runner.webdriver_element.submit,
            "WR_element_clear": web_runner.webdriver_element.clear,
            "WR_element_get_property": web_runner.webdriver_element.get_property,
            "WR_element_get_dom_attribute": web_runner.webdriver_element.get_dom_attribute,
            "WR_element_get_attribute": web_runner.webdriver_element.get_attribute,
            "WR_element_is_selected": web_runner.webdriver_element.is_selected,
            "WR_element_is_enabled": web_runner.webdriver_element.is_enabled,
            "WR_input_to_element": web_runner.webdriver_element.input_to_element,
            "WR_click_element": web_runner.webdriver_element.click_element,
            "WR_element_is_displayed": web_runner.webdriver_element.is_displayed,
            "WR_element_value_of_css_property": web_runner.webdriver_element.value_of_css_property,
            "WR_element_screenshot": web_runner.webdriver_element.screenshot,
            "WR_element_change_web_element": web_runner.webdriver_element.change_web_element,
            "WR_element_check_current_web_element": web_runner.webdriver_element.check_current_web_element,
            "WR_element_get_select": web_runner.webdriver_element.get_select,

            # init test record
            "WR_set_record_enable": test_record_instance.set_record_enable,

            # generate report
            "WR_generate_html": generate_html,
            "WR_generate_html_report": generate_html_report,
            "WR_generate_json": generate_json,
            "WR_generate_json_report": generate_json_report,
            "WR_generate_xml": generate_xml,
            "WR_generate_xml_report": generate_xml_report,
            "WR_generate_junit_xml": generate_junit_xml,
            "WR_generate_junit_xml_report": generate_junit_xml_report,

            # execute
            "WR_execute_action": self.execute_action,
            "WR_execute_files": self.execute_files,

            # validate
            "WR_validate_action_json": validate_action_json,
            "WR_validate_action_file": validate_action_file,

            # environment configuration
            "WR_load_env": load_env,
            "WR_get_env": get_env,
            "WR_expand_env_in_action": expand_in_action,

            # visual regression
            "WR_visual_capture_baseline": _visual_capture_baseline,
            "WR_visual_compare": _visual_compare,

            # browser recorder (auto-binds to webdriver_wrapper_instance)
            "WR_recorder_start": lambda: _recorder_start(webdriver_wrapper_instance),
            "WR_recorder_stop": lambda: _recorder_stop(webdriver_wrapper_instance),
            "WR_recorder_pull_events": lambda: _recorder_pull_events(webdriver_wrapper_instance),
            "WR_recorder_save": lambda output_path, raw_events_path=None: _recorder_save_recording(
                webdriver_wrapper_instance, output_path, raw_events_path
            ),

            # playwright backend — page-level operations
            "WR_pw_launch": _pw.pw_launch,
            "WR_pw_quit": _pw.pw_quit,
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

            # Add package
            "WR_add_package_to_executor": package_manager.add_package_to_executor,
            "WR_add_package_to_callback_executor": package_manager.add_package_to_callback_executor,
        }

        # 將安全的 Python 內建函式加入事件字典，過濾可執行任意程式碼者
        # Register safe Python builtins only; skip those that enable arbitrary
        # code execution or unrestricted I/O.
        for name, function in getmembers(builtins, isbuiltin):
            if name in _UNSAFE_BUILTINS:
                continue
            self.event_dict[name] = function

    def _execute_event(self, action: list):
        """
        執行事件字典中的函式
        Execute a function from event_dict

        :param action: 指令清單，例如 ["函式名稱", {參數}] 或 ["函式名稱"]
                       Action list, e.g., ["function_name", {params}] or ["function_name"]
        :return: 執行結果 / return value of the executed function
        """
        event = self.event_dict.get(action[0])
        if event is None:
            raise WebRunnerExecuteException(executor_data_error + " unknown command: " + str(action[0]))
        if len(action) == 2:
            if isinstance(action[1], dict):
                # 使用關鍵字參數呼叫
                # Call with keyword arguments
                return event(**action[1])
            else:
                # 使用位置參數呼叫
                # Call with positional arguments
                return event(*action[1])
        elif len(action) == 1:
            # 無參數呼叫
            # Call without arguments
            return event()
        else:
            # 格式錯誤，拋出例外
            # Invalid format, raise exception
            raise WebRunnerExecuteException(executor_data_error + " " + str(action))

    def execute_action(self, action_list: Union[list, dict]) -> dict:
        """
        執行一系列動作
        Execute a list of actions

        :param action_list: 動作清單，例如：
           Action list, e.g.:
           [
               ["WR_get_webdriver_manager", {"webdriver_name": "firefox"}],
               ["WR_to_url", {"url": "https://www.google.com"}],
               ["WR_quit"]
           ]
        :return: 執行紀錄字典 {動作描述: 回傳值}
                 Execution record dict {action: response}
        """
        web_runner_logger.info(f"execute_action, action_list: {action_list}")

        # 如果傳入的是 dict，則嘗試取出 "webdriver_wrapper" 的動作清單
        # If input is dict, extract "webdriver_wrapper" action list
        if type(action_list) is dict:
            action_list = action_list.get("webdriver_wrapper", None)
            if action_list is None:
                web_runner_logger.error(
                    f"execute_action, action_list: {action_list}, "
                    f"failed: {WebRunnerExecuteException(executor_list_error)}")
                raise WebRunnerExecuteException(executor_list_error)

        execute_record_dict = {}

        # 檢查 action_list 是否為合法的 list
        # Validate action_list
        try:
            if len(action_list) == 0 or isinstance(action_list, list) is False:
                web_runner_logger.error(
                    f"execute_action, action_list: {action_list}, "
                    f"failed: {WebRunnerExecuteException(executor_list_error)}")
                raise WebRunnerExecuteException(executor_list_error)
        except Exception as error:
            web_runner_logger.error(
                f"execute_action, action_list: {action_list}, "
                f"failed: {repr(error)}")

        # 逐一執行動作
        # Execute each action in the list
        for action in action_list:
            try:
                event_response = self._execute_event(action)
                execute_record = "execute: " + str(action)
                execute_record_dict.update({execute_record: event_response})
            except Exception as error:
                web_runner_logger.error(
                    f"execute_action, action_list: {action_list}, "
                    f"action: {action}, failed: {repr(error)}")
                execute_record = "execute: " + str(action)
                execute_record_dict.update({execute_record: repr(error)})

        # 輸出執行結果
        # Print execution results
        for key, value in execute_record_dict.items():
            print(key)
            print(value)

        return execute_record_dict

    def execute_files(self, execute_files_list: list) -> list:
        """
        從檔案載入並執行動作
        Execute actions from files

        :param execute_files_list: 檔案路徑清單 / list of file paths
        :return: 每個檔案的執行結果清單 / list of execution results
        """
        web_runner_logger.info(f"execute_files, execute_files_list: {execute_files_list}")
        execute_detail_list = []
        for file in execute_files_list:
            # 讀取 JSON 檔案並執行
            # Read JSON file and execute
            execute_detail_list.append(self.execute_action(read_action_json(file)))
        return execute_detail_list


# 建立全域 Executor 實例
# Create global Executor instance
executor = Executor()
package_manager.executor = executor

def add_command_to_executor(command_dict: dict):
    """
    動態新增指令到 Executor
    Dynamically add commands to Executor

    :param command_dict: {指令名稱: 函式} / {command_name: function}
    """
    for command_name, command in command_dict.items():
        if isinstance(command, (types.MethodType, types.FunctionType)):
            executor.event_dict.update({command_name: command})
        else:
            raise WebRunnerAddCommandException(add_command_exception_tag)

def execute_action(action_list: list) -> dict:
    """
    全域方法：執行動作清單
    Global method: execute action list
    """
    return executor.execute_action(action_list)

def execute_files(execute_files_list: list) -> list:
    """
    全域方法：執行檔案中的動作
    Global method: execute actions from files
    """
    return executor.execute_files(execute_files_list)