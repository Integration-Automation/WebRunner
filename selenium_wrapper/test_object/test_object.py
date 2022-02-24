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

    def __init__(self, test_object_name: str, object_type=None):
        self.object_type = object_type
        self.test_object_name: str = test_object_name
        if self.object_type not in type_list:
            raise TypeError


def create_test_object(object_type, test_object_name: str):
    return TestObject(object_type, test_object_name)

def get_test_object_type_list():
    return type_list
