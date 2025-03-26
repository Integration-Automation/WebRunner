import typing
from sys import stderr

from je_web_runner.utils.executor.action_executor import execute_action, execute_files

from je_web_runner.utils.generate_report.generate_html_report import generate_html, generate_html_report
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml, generate_xml_report
from je_web_runner.utils.generate_report.generate_json_report import generate_json, generate_json_report
from je_web_runner.utils.package_manager.package_manager_class import package_manager

from je_web_runner.utils.test_record.test_record_class import test_record_instance

from je_web_runner.manager.webrunner_manager import web_runner
from je_web_runner.utils.exception.exception_tags import get_bad_trigger_function, get_bad_trigger_method
from je_web_runner.utils.exception.exceptions import CallbackExecutorException
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


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