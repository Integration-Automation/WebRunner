import builtins
import types
from inspect import getmembers, isbuiltin
from typing import Union, Any

from je_web_runner.je_web_runner.manager.webrunner_manager import web_runner
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
from je_web_runner.utils.scheduler.extend_apscheduler import scheduler_manager
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.test_record.test_record_class import test_record_instance


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
            "WR_set_driver": web_runner.webdriver_wrapper.set_driver,
            "WR_set_webdriver_options_capability": web_runner.webdriver_wrapper.set_driver,
            "WR_find_element": web_runner.webdriver_wrapper.find_element_with_test_object_record,
            "WR_find_elements": web_runner.webdriver_wrapper.find_elements_with_test_object_record,
            "WR_implicitly_wait": web_runner.webdriver_wrapper.implicitly_wait,
            "WR_explict_wait": web_runner.webdriver_wrapper.explict_wait,
            "WR_to_url": web_runner.webdriver_wrapper.to_url,
            "WR_forward": web_runner.webdriver_wrapper.forward,
            "WR_back": web_runner.webdriver_wrapper.back,
            "WR_refresh": web_runner.webdriver_wrapper.refresh,
            "WR_switch": web_runner.webdriver_wrapper.switch,
            "WR_set_script_timeout": web_runner.webdriver_wrapper.set_script_timeout,
            "WR_set_page_load_timeout": web_runner.webdriver_wrapper.set_page_load_timeout,
            "WR_get_cookies": web_runner.webdriver_wrapper.get_cookies,
            "WR_get_cookie": web_runner.webdriver_wrapper.get_cookie,
            "WR_add_cookie": web_runner.webdriver_wrapper.add_cookie,
            "WR_delete_cookie": web_runner.webdriver_wrapper.delete_cookie,
            "WR_delete_all_cookies": web_runner.webdriver_wrapper.delete_all_cookies,
            "WR_execute": web_runner.webdriver_wrapper.execute,
            "WR_execute_script": web_runner.webdriver_wrapper.execute_script,
            "WR_execute_async_script": web_runner.webdriver_wrapper.execute_async_script,
            "WR_move_to_element": web_runner.webdriver_wrapper.move_to_element_with_test_object,
            "WR_move_to_element_with_offset": web_runner.webdriver_wrapper.move_to_element_with_offset_and_test_object,
            "WR_drag_and_drop": web_runner.webdriver_wrapper.drag_and_drop_with_test_object,
            "WR_drag_and_drop_offset": web_runner.webdriver_wrapper.drag_and_drop_offset_with_test_object,
            "WR_perform": web_runner.webdriver_wrapper.perform,
            "WR_reset_actions": web_runner.webdriver_wrapper.reset_actions,
            "WR_left_click": web_runner.webdriver_wrapper.left_click_with_test_object,
            "WR_left_click_and_hold": web_runner.webdriver_wrapper.left_click_and_hold_with_test_object,
            "WR_right_click": web_runner.webdriver_wrapper.right_click_with_test_object,
            "WR_left_double_click": web_runner.webdriver_wrapper.left_double_click_with_test_object,
            "WR_release": web_runner.webdriver_wrapper.release_with_test_object,
            "WR_press_key": web_runner.webdriver_wrapper.press_key_with_test_object,
            "WR_release_key": web_runner.webdriver_wrapper.release_key_with_test_object,
            "WR_move_by_offset": web_runner.webdriver_wrapper.move_by_offset,
            "WR_pause": web_runner.webdriver_wrapper.pause,
            "WR_send_keys": web_runner.webdriver_wrapper.send_keys,
            "WR_send_keys_to_element": web_runner.webdriver_wrapper.send_keys_to_element_with_test_object,
            "WR_scroll": web_runner.webdriver_wrapper.scroll,
            "WR_check_current_webdriver": web_runner.webdriver_wrapper.check_current_webdriver,
            "WR_maximize_window": web_runner.webdriver_wrapper.maximize_window,
            "WR_fullscreen_window": web_runner.webdriver_wrapper.fullscreen_window,
            "WR_minimize_window": web_runner.webdriver_wrapper.minimize_window,
            "WR_set_window_size": web_runner.webdriver_wrapper.set_window_size,
            "WR_set_window_position": web_runner.webdriver_wrapper.set_window_position,
            "WR_get_window_position": web_runner.webdriver_wrapper.get_window_position,
            "WR_get_window_rect": web_runner.webdriver_wrapper.get_window_rect,
            "WR_set_window_rect": web_runner.webdriver_wrapper.set_window_rect,
            "WR_get_screenshot_as_png": web_runner.webdriver_wrapper.get_screenshot_as_png,
            "WR_get_screenshot_as_base64": web_runner.webdriver_wrapper.get_screenshot_as_base64,
            "WR_get_log": web_runner.webdriver_wrapper.get_log,
            "WR_single_quit": web_runner.webdriver_wrapper.quit,
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
            # Scheduler
            "WR_scheduler_event_trigger": self.scheduler_event_trigger,
            "WR_remove_blocking_scheduler_job": scheduler_manager.remove_blocking_job,
            "WR_remove_nonblocking_scheduler_job": scheduler_manager.remove_nonblocking_job,
            "WR_start_blocking_scheduler": scheduler_manager.start_block_scheduler,
            "WR_start_nonblocking_scheduler": scheduler_manager.start_nonblocking_scheduler,
            "WR_start_all_scheduler": scheduler_manager.start_all_scheduler,
            "WR_shutdown_blocking_scheduler": scheduler_manager.shutdown_blocking_scheduler,
            "WR_shutdown_nonblocking_scheduler": scheduler_manager.shutdown_nonblocking_scheduler,
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

    def scheduler_event_trigger(
            self, function: str, id: str = None, args: Union[list, tuple] = None,
            kwargs: dict = None, scheduler_type: str = "nonblocking", wait_type: str = "secondly",
            wait_value: int = 1, **trigger_args: Any) -> None:
        if scheduler_type == "nonblocking":
            scheduler_event = scheduler_manager.nonblocking_scheduler_event_dict.get(wait_type)
        else:
            scheduler_event = scheduler_manager.blocking_scheduler_event_dict.get(wait_type)
        scheduler_event(self.event_dict.get(function), id, args, kwargs, wait_value, **trigger_args)


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
