import builtins
import types
from inspect import getmembers, isbuiltin

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
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.package_manager.package_manager_class import package_manager
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class Executor(object):

    def __init__(self):
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
            "WR_set_webdriver_options_capability": webdriver_wrapper_instance.set_driver,
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
            # execute
            "WR_execute_action": self.execute_action,
            "WR_execute_files": self.execute_files,
            # Add package
            "WR_add_package_to_executor": package_manager.add_package_to_executor,
            "WR_add_package_to_callback_executor": package_manager.add_package_to_callback_executor,
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
            ["WR_get_webdriver_manager", {"webdriver_name": "firefox"}],
            ["WR_to_url", {"url": "https://www.google.com"}],
            ["WR_quit"]
        ]
        for loop and use execute_event function to execute
        :return: recode string, response as list
        """
        web_runner_logger.info(f"execute_action, action_list: {action_list}")
        if type(action_list) is dict:
            action_list = action_list.get("webdriver_wrapper", None)
            if action_list is None:
                web_runner_logger.error(
                    f"execute_action, action_list: {action_list}, "
                    f"failed: {WebRunnerExecuteException(executor_list_error)}")
                raise WebRunnerExecuteException(executor_list_error)
        execute_record_dict = dict()
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
