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
            "WR_execute_action": execute_action,
            "WR_execute_files": execute_files,
            # Add package
            "WR_add_package_to_executor": package_manager.add_package_to_executor,
            "WR_add_package_to_callback_executor": package_manager.add_package_to_callback_executor,
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