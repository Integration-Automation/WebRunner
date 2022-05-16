from je_web_runner import TestObject
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record

test_object_record.save_test_object("q", "name")
test_object_record.save_test_object("test_name", "name")
q_test_object: TestObject = test_object_record.test_object_record_dict.get("q")
test_name_test_object: TestObject = test_object_record.test_object_record_dict.get("test_name")
print(q_test_object)
print(test_name_test_object)
print(q_test_object.test_object_name)
print(q_test_object.test_object_type)
print(test_name_test_object.test_object_name)
print(test_name_test_object.test_object_type)
assert q_test_object is not None
assert test_name_test_object is not None
assert q_test_object.test_object_name == "q"
assert q_test_object.test_object_type == "name"
assert test_name_test_object.test_object_name == "test_name"
assert test_name_test_object.test_object_type == "name"
