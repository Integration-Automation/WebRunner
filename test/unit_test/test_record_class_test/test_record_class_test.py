from je_web_runner import TestObject
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


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
_check(q_test_object is not None, "q_test_object is None")
_check(test_name_test_object is not None, "test_name_test_object is None")
_check(q_test_object.test_object_name == "q", "q_test_object name mismatch")
_check(q_test_object.test_object_type == "name", "q_test_object type mismatch")
_check(test_name_test_object.test_object_name == "test_name", "test_name name mismatch")
_check(test_name_test_object.test_object_type == "name", "test_name type mismatch")
