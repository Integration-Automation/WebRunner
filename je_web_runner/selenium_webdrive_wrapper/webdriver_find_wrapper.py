from je_web_runner.test_object.test_object import TestObject
from je_web_runner.utils.test_object_record.test_object_record import test_object_record


def find_element_wrapper(webdriver, test_object: TestObject):
    return webdriver.find_element(test_object.test_object_type, test_object.test_object_name)


def find_elements_wrapper(webdriver, test_object: TestObject):
    return webdriver.find_elements(test_object.test_object_type, test_object.test_object_name)


def find_element_with_test_object_record(webdriver, test_object_name: str):
    return webdriver.find_element(
        test_object_record.get(test_object_name).test_object_type,
        test_object_record.get(test_object_name).test_object_name
    )


def find_elements_with_test_object_record(webdriver, test_object_name: str):
    return webdriver.find_elements(
        test_object_record.get(test_object_name).test_object_type,
        test_object_record.get(test_object_name).test_object_name
    )
