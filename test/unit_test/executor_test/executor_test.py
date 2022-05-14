from je_web_runner import execute_action

test_execute_list = [
    ["get_webdriver_manager", {"webdriver_name": "firefox"}],
    ["to_url", {"url": "https://www.google.com"}],
    ["SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
    ["implicitly_wait", {"time_to_wait": 3}],
    ["find_element", {"element_name": "q"}],
    ["click_element"],
    ["implicitly_wait", {"time_to_wait": 3}],
    ["input_to_element", {"input_value": "test 123 test do you read"}],
    ["quit"],
]

execute_action(test_execute_list)
