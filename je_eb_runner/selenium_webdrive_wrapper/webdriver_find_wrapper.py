from je_eb_runner.test_object.test_object import TestObject


def find_element_wrapper(webdriver, test_object: TestObject):
    return webdriver.find_element(test_object.test_object_type, test_object.test_object_name)


def find_elements_wrapper(webdriver, test_object: TestObject):
    return webdriver.find_elements(test_object.test_object_type, test_object.test_object_name)
