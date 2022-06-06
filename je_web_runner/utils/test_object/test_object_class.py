from selenium.webdriver.common.by import By

type_list = [
    By.ID,
    By.CSS_SELECTOR,
    By.NAME,
    By.XPATH,
    By.TAG_NAME,
    By.CLASS_NAME,
    By.LINK_TEXT
]


class TestObject(object):
    """
    use to create data class
    """

    def __init__(self, test_object_name: str, object_type: str):
        self.test_object_type: str = object_type
        self.test_object_name: str = test_object_name
        if self.test_object_type not in type_list:
            raise TypeError


def create_test_object(object_type, test_object_name: str) -> TestObject:
    """
    :param object_type: test object type should in type_list
    :param test_object_name: this test object name
    :return: test object
    """
    return TestObject(object_type, test_object_name)


def get_test_object_type_list() -> list:
    """
    :return: list include what type should be used to create test object
    """
    return type_list
