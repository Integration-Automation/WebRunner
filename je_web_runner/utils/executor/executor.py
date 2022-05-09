import sys

from je_web_runner.selenium_webdrive_wrapper.get_webdrivers import get_webdriver_manager
from je_web_runner.utils.exception.exception_tag import executor_data_error, executor_list_error
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.test_object_record.test_object_record import test_object_record
from je_web_runner.selenium_webdrive_wrapper.webdriver_find_wrapper import find_element_with_test_object_record
from je_web_runner.selenium_webdrive_wrapper.webdriver_find_wrapper import find_elements_with_test_object_record

event_dict = {
    "get_webdriver_manager": get_webdriver_manager,
    "TestObject": test_object_record.save_test_object,
    "": ""
}


def execute_event(action: list):
    """
    :param action: execute action
    :return: what event return
    """
    event = event_dict.get(action[0])
    if len(action) == 2:
        return event(**action[1])
    else:
        raise WebRunnerExecuteException(executor_data_error)


def execute_action(action_list: list):
    """
    :param action_list: like this structure
    [

    ]
    for loop and use execute_event function to execute
    :return: recode string, response as list
    """
    execute_record_string = ""
    event_response_list = []
    try:
        if len(action_list) > 0 or type(action_list) is not list:
            for action in action_list:
                event_response = execute_event(action)
                print("execute: ", str(action))
                execute_record_string = "".join(execute_record_string)
                event_response_list.append(event_response)
        else:
            raise WebRunnerExecuteException(executor_list_error)
        return execute_record_string, event_response_list
    except Exception as error:
        print(repr(error), file=sys.stderr)


def execute_files(execute_files_list: list):
    """
    :param execute_files_list: list include execute files path
    :return: every execute detail as list
    """
    execute_detail_list = list()
    for file in execute_files_list:
        execute_detail_list.append(execute_action(read_action_json(file)))
    return execute_detail_list
