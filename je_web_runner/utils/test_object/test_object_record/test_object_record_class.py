from typing import Union

from je_web_runner.utils.test_object.test_object_class import TestObject


class TestObjectRecord(object):
    """
    測試物件紀錄管理器
    Test object record manager
    """

    def __init__(self):
        # 用來儲存測試物件的字典
        # Dictionary to store test objects
        # key: test_object_name, value: TestObject instance
        self.test_object_record_dict = dict()

    def clean_record(self) -> None:
        """
        清空所有測試物件紀錄
        Clear all test object records
        """
        self.test_object_record_dict = dict()

    def save_test_object(self, test_object_name: str, object_type: str = None, **kwargs) -> None:
        """
        儲存新的測試物件
        Save a new test object

        :param test_object_name: 測試物件名稱 / test object name
        :param object_type: 測試物件類型 (可選) / test object type (optional)
        :param kwargs: 額外參數 (目前未使用) / extra parameters (currently unused)
        """
        test_object = TestObject(test_object_name, object_type)
        self.test_object_record_dict.update({test_object.test_object_name: test_object})

    def remove_test_object(self, test_object_name: str) -> Union[TestObject, bool]:
        """
        移除指定名稱的測試物件
        Remove a test object by name

        :param test_object_name: 測試物件名稱 / test object name
        :return: 被移除的 TestObject，若不存在則回傳 False
                 Removed TestObject if exists, otherwise False
        """
        return self.test_object_record_dict.pop(test_object_name, False)


# 全域單例，用來管理測試物件紀錄
# Global singleton instance to manage test object records
test_object_record = TestObjectRecord()