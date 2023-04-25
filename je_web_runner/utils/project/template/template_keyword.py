template_keyword_1: list = [
    ["get_webdriver_manager", {"webdriver_name": "firefox"}],
    ["add_package_to_executor", ["time"]],
    ["time_sleep", [1]],
    ["minimize_window"],
    ["time_sleep", [1]],
    ["maximize_window"],
    ["quit"]
]

template_keyword_2: list = [
    ["get_webdriver_manager", {"webdriver_name": "firefox"}],
    ["maximize_window"],
    ["add_package_to_executor", ["time"]],
    ["SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
    ["find_element", {"element_name": "q"}],
    ["click_element"],
    ["input_to_element", {"input_value": "test 123 test"}],
    ["time_sleep", [3]],
    ["quit"]
]

bad_template_1 = [
    ["set_record_enable", [True]],
    ["add_package_to_executor", ["os"]],
    ["os_system", ["python --version"]],
    ["os_system", ["python -m pip --version"]],
]
