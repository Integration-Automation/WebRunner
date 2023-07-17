template_keyword_1: list = [
    ["WR_get_webdriver_manager", {"webdriver_name": "firefox"}],
    ["WR_add_package_to_executor", ["time"]],
    ["time_sleep", [1]],
    ["WR_minimize_window"],
    ["time_sleep", [1]],
    ["WR_maximize_window"],
    ["WR_quit"]
]

template_keyword_2: list = [
    ["WR_get_webdriver_manager", {"webdriver_name": "firefox"}],
    ["WR_maximize_window"],
    ["WR_add_package_to_executor", ["time"]],
    ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
    ["WR_find_element", {"element_name": "q"}],
    ["WR_click_element"],
    ["WR_input_to_element", {"input_value": "test 123 test"}],
    ["time_sleep", [3]],
    ["WR_quit"]
]

bad_template_1 = [
    ["WR_set_record_enable", [True]],
    ["WR_add_package_to_executor", ["os"]],
    ["os_system", ["python --version"]],
    ["os_system", ["python -m pip --version"]],
]
