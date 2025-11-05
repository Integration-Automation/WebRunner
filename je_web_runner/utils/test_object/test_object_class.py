from selenium.webdriver.common.by import By

# 可用的定位方式清單
# List of available locator strategies
type_list = dir(By)


class TestObject(object):
    """
    測試物件類別，用來封裝定位資訊
    TestObject class, used to encapsulate locator information
    """

    def __init__(self, object_type: str, test_object_name: str):
        # 測試物件的定位方式 (必須在 type_list 中)
        # Locator type of the test object (must be in type_list)
        self.test_object_type: str = object_type

        # 測試物件名稱 (實際的定位值，例如元素 ID 或 XPath)
        # Locator value of the test object (e.g., element ID or XPath)
        self.test_object_name: str = test_object_name

        # 驗證定位方式是否合法
        # Validate locator type
        if self.test_object_type not in type_list:
            raise TypeError(f"Invalid locator type: {self.test_object_type}")


def create_test_object(object_type: str, test_object_name: str) -> TestObject:
    """
    建立一個新的測試物件
    Create a new TestObject

    :param object_type: 測試物件的定位方式 (必須在 type_list 中)
                        Locator type (must be in type_list)
    :param test_object_name: 測試物件名稱 (定位值)
                             Locator value
    :return: TestObject 實例 / TestObject instance
    """
    return TestObject(test_object_name, object_type)


def get_test_object_type_list() -> list:
    """
    取得所有可用的定位方式
    Get all available locator strategies

    :return: 包含所有定位方式的清單
             List of available locator strategies
    """
    return type_list