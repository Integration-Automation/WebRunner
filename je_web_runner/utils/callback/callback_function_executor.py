import typing
from sys import stderr

from je_web_runner.utils.executor.action_executor import execute_action, execute_files

from je_web_runner.utils.generate_report.generate_html_report import generate_html, generate_html_report
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml, generate_xml_report
from je_web_runner.utils.generate_report.generate_json_report import generate_json, generate_json_report
from je_web_runner.utils.package_manager.package_manager_class import package_manager

from je_web_runner.utils.test_record.test_record_class import test_record_instance

from je_web_runner.je_web_runner.manager.webrunner_manager import web_runner
from je_web_runner.utils.exception.exception_tags import get_bad_trigger_function, get_bad_trigger_method
from je_web_runner.utils.exception.exceptions import CallbackExecutorException
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record


class CallbackFunctionExecutor(object):

    def __init__(self):
        self.event_dict: dict = {
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
            "fullscreen_window": web_runner.webdriver_wrapper.full_screen_window,
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
            "execute_action": execute_action,
            "execute_files": execute_files,
            # Add package
            "add_package_to_executor": package_manager.add_package_to_executor,
            "add_package_to_callback_executor": package_manager.add_package_to_callback_executor,
        }

    def callback_function(
            self,
            trigger_function_name: str,
            callback_function: typing.Callable,
            callback_function_param: [dict, None] = None,
            callback_param_method: str = "kwargs",
            **kwargs
    ):
        """
        :param trigger_function_name: what function we want to trigger only accept function in event_dict
        :param callback_function: what function we want to callback
        :param callback_function_param: callback function's param only accept dict
        :param callback_param_method: what type param will use on callback function only accept kwargs and args
        :param kwargs: trigger_function's param
        :return: trigger_function_name return value
        """
        try:
            if trigger_function_name not in self.event_dict.keys():
                raise CallbackExecutorException(get_bad_trigger_function)
            execute_return_value = self.event_dict.get(trigger_function_name)(**kwargs)
            if callback_function_param is not None:
                if callback_param_method not in ["kwargs", "args"]:
                    raise CallbackExecutorException(get_bad_trigger_method)
                if callback_param_method == "kwargs":
                    callback_function(**callback_function_param)
                else:
                    callback_function(*callback_function_param)
            else:
                callback_function()
            return execute_return_value
        except Exception as error:
            print(repr(error), file=stderr)


callback_executor = CallbackFunctionExecutor()