import builtins
import sys
import time
import types
from inspect import getmembers, isbuiltin

from je_web_runner.je_web_runner.manager.webrunner_manager import web_runner
from je_web_runner.utils.exception.exception_tags import add_command_exception_tag
from je_web_runner.utils.exception.exception_tags import executor_data_error, executor_list_error
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException, WebRunnerAddCommandException
from je_web_runner.utils.generate_report.generate_html_report import generate_html_report
from je_web_runner.utils.generate_report.generate_html_report import generate_html
from je_web_runner.utils.generate_report.generate_json_report import generate_json
from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml_report
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.package_manager.package_manager_class import package_manager
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.test_record.test_record_class import test_record_instance


class Executor(object):

    def __init__(self):
        self.event_dict = {
            # webdriver manager
            "get_webdriver_manager": web_runner.new_driver,
            "change_index_of_webdriver": web_runner.change_webdriver,
            "quit": web_runner.quit,
            # test object
            "SaveTestObject": test_object_record.save_test_object,
            "CleanTestObject": test_object_record.clean_record,
            # webdriver wrapper
            "set_driver": web_runner.webdriver_wrapper.set_driver,
            "set_webdriver_options_capability": web_runner.webdriver_wrapper.set_driver,
            "find_element": web_runner.webdriver_wrapper.find_element_with_test_object_record,
            "find_elements": web_runner.webdriver_wrapper.find_elements_with_test_object_record,
            "implicitly_wait": web_runner.webdriver_wrapper.implicitly_wait,
            "explict_wait": web_runner.webdriver_wrapper.explict_wait,
            "to_url": web_runner.webdriver_wrapper.to_url,
            "forward": web_runner.webdriver_wrapper.forward,
            "back": web_runner.webdriver_wrapper.back,
            "refresh": web_runner.webdriver_wrapper.refresh,
            "switch": web_runner.webdriver_wrapper.switch,
            "set_script_timeout": web_runner.webdriver_wrapper.set_script_timeout,
            "set_page_load_timeout": web_runner.webdriver_wrapper.set_page_load_timeout,
            "get_cookies": web_runner.webdriver_wrapper.get_cookies,
            "get_cookie": web_runner.webdriver_wrapper.get_cookie,
            "add_cookie": web_runner.webdriver_wrapper.add_cookie,
            "delete_cookie": web_runner.webdriver_wrapper.delete_cookie,
            "delete_all_cookies": web_runner.webdriver_wrapper.delete_all_cookies,
            "execute": web_runner.webdriver_wrapper.execute,
            "execute_script": web_runner.webdriver_wrapper.execute_script,
            "execute_async_script": web_runner.webdriver_wrapper.execute_async_script,
            "move_to_element": web_runner.webdriver_wrapper.move_to_element_with_test_object,
            "move_to_element_with_offset": web_runner.webdriver_wrapper.move_to_element_with_offset_and_test_object,
            "drag_and_drop": web_runner.webdriver_wrapper.drag_and_drop_with_test_object,
            "drag_and_drop_offset": web_runner.webdriver_wrapper.drag_and_drop_offset_with_test_object,
            "perform": web_runner.webdriver_wrapper.perform,
            "reset_actions": web_runner.webdriver_wrapper.reset_actions,
            "left_click": web_runner.webdriver_wrapper.left_click_with_test_object,
            "left_click_and_hold": web_runner.webdriver_wrapper.left_click_and_hold_with_test_object,
            "right_click": web_runner.webdriver_wrapper.right_click_with_test_object,
            "left_double_click": web_runner.webdriver_wrapper.left_double_click_with_test_object,
            "release": web_runner.webdriver_wrapper.release_with_test_object,
            "press_key": web_runner.webdriver_wrapper.press_key_with_test_object,
            "release_key": web_runner.webdriver_wrapper.release_key_with_test_object,
            "move_by_offset": web_runner.webdriver_wrapper.move_by_offset,
            "pause": web_runner.webdriver_wrapper.pause,
            "send_keys": web_runner.webdriver_wrapper.send_keys,
            "send_keys_to_element": web_runner.webdriver_wrapper.send_keys_to_element_with_test_object,
            "scroll": web_runner.webdriver_wrapper.scroll,
            "check_current_webdriver": web_runner.webdriver_wrapper.check_current_webdriver,
            "maximize_window": web_runner.webdriver_wrapper.maximize_window,
            "fullscreen_window": web_runner.webdriver_wrapper.fullscreen_window,
            "minimize_window": web_runner.webdriver_wrapper.minimize_window,
            "set_window_size": web_runner.webdriver_wrapper.set_window_size,
            "set_window_position": web_runner.webdriver_wrapper.set_window_position,
            "get_window_position": web_runner.webdriver_wrapper.get_window_position,
            "get_window_rect": web_runner.webdriver_wrapper.get_window_rect,
            "set_window_rect": web_runner.webdriver_wrapper.set_window_rect,
            "get_screenshot_as_png": web_runner.webdriver_wrapper.get_screenshot_as_png,
            "get_screenshot_as_base64": web_runner.webdriver_wrapper.get_screenshot_as_base64,
            "get_log": web_runner.webdriver_wrapper.get_log,
            "single_quit": web_runner.webdriver_wrapper.quit,
            # web element
            "element_submit": web_runner.webdriver_element.submit,
            "element_clear": web_runner.webdriver_element.clear,
            "element_get_property": web_runner.webdriver_element.get_property,
            "element_get_dom_attribute": web_runner.webdriver_element.get_dom_attribute,
            "element_get_attribute": web_runner.webdriver_element.get_attribute,
            "element_is_selected": web_runner.webdriver_element.is_selected,
            "element_is_enabled": web_runner.webdriver_element.is_enabled,
            "input_to_element": web_runner.webdriver_element.input_to_element,
            "click_element": web_runner.webdriver_element.click_element,
            "element_is_displayed": web_runner.webdriver_element.is_displayed,
            "element_value_of_css_property": web_runner.webdriver_element.value_of_css_property,
            "element_screenshot": web_runner.webdriver_element.screenshot,
            "element_change_web_element": web_runner.webdriver_element.change_web_element,
            "element_check_current_web_element": web_runner.webdriver_element.check_current_web_element,
            "element_get_select": web_runner.webdriver_element.get_select,
            # init test record
            "set_record_enable": test_record_instance.set_record_enable,
            # generate report
            "generate_html": generate_html,
            "generate_html_report": generate_html_report,
            "generate_json": generate_json,
            "generate_json_report": generate_json_report,
            "generate_xml": generate_xml,
            "generate_xml_report": generate_xml_report,
            # execute
            "execute_action": self.execute_action,
            "execute_files": self.execute_files,
            # Add package
            "add_package_to_executor": package_manager.add_package_to_executor,
            "add_package_to_callback_executor": package_manager.add_package_to_callback_executor,
        }
        # get all builtin function and add to event dict
        for function in getmembers(builtins, isbuiltin):
            self.event_dict.update({str(function[0]): function[1]})

    def _execute_event(self, action: list):
        """
        :param action: execute action
        :return: what event return
        """
        event = self.event_dict.get(action[0])
        if len(action) == 2:
            if isinstance(action[1], dict):
                return event(**action[1])
            else:
                return event(*action[1])
        elif len(action) == 1:
            return event()
        else:
            raise WebRunnerExecuteException(executor_data_error + " " + str(action))

    def execute_action(self, action_list: [list, dict]) -> dict:
        """
        use to execute action on list
        :param action_list: like this structure
        [
            ["get_webdriver_manager", {"webdriver_name": "firefox"}],
            ["to_url", {"url": "https://www.google.com"}],
            ["quit"]
        ]
        for loop and use execute_event function to execute
        :return: recode string, response as list
        """
        web_runner_logger.info(f"execute_action, action_list: {action_list}")
        if type(action_list) is dict:
            action_list = action_list.get("web_runner", None)
            if action_list is None:
                web_runner_logger.error(
                    f"execute_action, action_list: {action_list}, "
                    f"failed: {WebRunnerExecuteException(executor_list_error)}")
                raise WebRunnerExecuteException(executor_list_error)
        execute_record_dict = dict()
        try:
            if len(action_list) > 0 or type(action_list) is not list:
                pass
            else:
                web_runner_logger.error(
                    f"execute_action, action_list: {action_list}, "
                    f"failed: {WebRunnerExecuteException(executor_list_error)}")
                raise WebRunnerExecuteException(executor_list_error)
        except Exception as error:
            web_runner_logger.error(
                f"execute_action, action_list: {action_list}, "
                f"failed: {repr(error)}")
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
        for key, value in execute_record_dict.items():
            print(key)
            print(value)
        return execute_record_dict

    def execute_files(self, execute_files_list: list) -> list:
        """
        :param execute_files_list: list include execute files path
        :return: every execute detail as list
        """
        web_runner_logger.info(f"execute_files, execute_files_list: {execute_files_list}")
        execute_detail_list = list()
        for file in execute_files_list:
            execute_detail_list.append(self.execute_action(read_action_json(file)))
        return execute_detail_list


executor = Executor()
package_manager.executor = executor


def add_command_to_executor(command_dict: dict):
    """
    :param command_dict: command dict to add into executor command dict
    :return:None
    """
    for command_name, command in command_dict.items():
        if isinstance(command, (types.MethodType, types.FunctionType)):
            executor.event_dict.update({command_name: command})
        else:
            raise WebRunnerAddCommandException(add_command_exception_tag)


def execute_action(action_list: list) -> dict:
    return executor.execute_action(action_list)


def execute_files(execute_files_list: list) -> list:
    return executor.execute_files(execute_files_list)
