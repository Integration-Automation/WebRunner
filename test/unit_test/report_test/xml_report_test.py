import sys

from je_web_runner import execute_action

test_execute_list = [
    ["set_record_enable", {"set_enable": True}],
    ["get_webdriver_manager", {"webdriver_name": "firefox"}],
    ["to_url", {"url": "https://www.google.com"}],
    ["SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
    ["implicitly_wait", {"time_to_wait": 3}],
    ["find_element", {"element_name": "q"}],
    ["click_element"],
    ["implicitly_wait", {"time_to_wait": 3}],
    ["input_to_element", {"input_value": "test 123 test do you read"}],
]

execute_action(test_execute_list)

test_execute_list = [
    ["to_url", {"url": "https://www.google.com"}],
    ["move_to_element", {"element_name": "q"}],
    ["implicitly_wait", {"time_to_wait": 3}],
    ["move_to_element_with_offset", {"element_name": "q", "offset_x": 10, "offset_y": 10}],
    ["move_by_offset", {"offset_x": 10, "offset_y": 10}],
    ["drag_and_drop", {"element_name": "q", "target_element_name": "q"}],
    ["drag_and_drop_offset", {"element_name": "q", "offset_x": 10, "offset_y": 10}],
    ["perform"],
    ["left_click", {"element_name": "q"}],
    ["release", {"element_name": "q"}],
    ["left_click"],
    ["release"],
    ["left_double_click"],
    ["release"],
    ["left_double_click"],
    ["left_click_and_hold"],
    ["press_key", {"keycode_on_key_class": "\ue031"}],
    ["release_key", {"keycode_on_key_class": "\ue031"}],
    ["send_keys", {"keys_to_send": "\ue031"}],
    ["send_keys_to_element", {"element_name": "q", "keys_to_send": "\ue031"}],
    ["perform"],
    ["pause", {"seconds": "3"}],
    ["pause", {"seconds": "dwadawdwaddwa"}]
]
execute_action(test_execute_list)

try:
    test_execute_list = [
        ["dwadwdadwdaw", {"dwadwadadw": "dwadawdawddwadwadawddaw"}]
    ]
    execute_action(test_execute_list)
except Exception as error:
    print(repr(error), file=sys.stderr)
finally:
    test_execute_list = [
        ["quit"],
        ["generate_xml_report"]
    ]
    execute_action(test_execute_list)
