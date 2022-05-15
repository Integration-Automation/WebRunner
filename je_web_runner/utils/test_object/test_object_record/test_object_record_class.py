from je_web_runner.utils.test_object.test_object_class import TestObject


class TestObjectRecord(object):

    def __init__(self):
        self.test_object_record_dict = dict()

    def clean_record(self):
        self.test_object_record_dict = dict()

    def save_test_object(self, test_object_name: str, object_type=None, **kwargs):
        test_object = TestObject(test_object_name, object_type)
        self.test_object_record_dict.update({test_object.test_object_name: test_object})


test_object_record = TestObjectRecord()
