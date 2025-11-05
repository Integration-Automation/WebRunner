import sys

from je_web_runner import create_test_object

try:
    new_test_object = create_test_object("id", "test_object")
    print(new_test_object.test_object_type)
    print(new_test_object.test_object_name)

    assert new_test_object.test_object_type == "id"
    assert new_test_object.test_object_name == "test_object"
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)
