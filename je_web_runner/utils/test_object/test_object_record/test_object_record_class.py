from typing import Any

from je_web_runner.utils.test_object.test_object_class import TestObject


class TestObjectRecord(object):

    def __init__(self):
        self.test_object_record_dict = dict()

    def clean_record(self) -> None:
        self.test_object_record_dict = dict()

    def save_test_object(self, test_object_name: str, object_type=None, **kwargs) -> None:
        test_object = TestObject(test_object_name, object_type)
        self.test_object_record_dict.update({test_object.test_object_name: test_object})

    def remove_test_object(self, test_object_name: str) -> Any:
        return self.test_object_record_dict.pop(test_object_name, False)


test_object_record = TestObjectRecord()
