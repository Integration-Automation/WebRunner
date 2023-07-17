import sys

from je_web_runner import execute_action

test_execute_list = [
    ["WR_set_record_enable", {"set_enable": True}],
    ["WR_get_webdriver_manager", {"webdriver_name": "firefox"}],
    ["WR_to_url", {"url": "https://www.google.com"}],
    ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
    ["WR_implicitly_wait", {"time_to_wait": 3}],
    ["WR_find_element", {"element_name": "q"}],
    ["WR_click_element"],
    ["WR_implicitly_wait", {"time_to_wait": 3}],
    ["WR_input_to_element", {"input_value": "test 123 test do you read"}],
]

execute_action(test_execute_list)

test_execute_list = [
    ["WR_to_url", {"url": "https://www.google.com"}],
    ["WR_move_to_element", {"element_name": "q"}],
    ["WR_implicitly_wait", {"time_to_wait": 3}],
    ["WR_move_to_element_with_offset", {"element_name": "q", "offset_x": 10, "offset_y": 10}],
    ["WR_move_by_offset", {"offset_x": 10, "offset_y": 10}],
    ["WR_drag_and_drop", {"element_name": "q", "target_element_name": "q"}],
    ["WR_drag_and_drop_offset", {"element_name": "q", "offset_x": 10, "offset_y": 10}],
    ["WR_perform"],
    ["WR_left_click", {"element_name": "q"}],
    ["WR_release", {"element_name": "q"}],
    ["WR_left_click"],
    ["WR_release"],
    ["WR_left_double_click"],
    ["WR_release"],
    ["WR_left_double_click"],
    ["WR_left_click_and_hold"],
    ["WR_press_key", {"keycode_on_key_class": "\ue031"}],
    ["WR_release_key", {"keycode_on_key_class": "\ue031"}],
    ["WR_send_keys", {"keys_to_send": "\ue031"}],
    ["WR_send_keys_to_element", {"element_name": "q", "keys_to_send": "\ue031"}],
    ["WR_perform"],
    ["WR_pause", {"seconds": "3"}],
    ["WR_pause", {"seconds": "dwadawdwaddwa"}]
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
        ["WR_quit"],
        ["WR_generate_html_report"]
    ]
    execute_action(test_execute_list)
