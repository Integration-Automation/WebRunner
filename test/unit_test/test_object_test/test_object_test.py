import sys

from je_web_runner import create_test_object


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


try:
    new_test_object = create_test_object("id", "test_object")
    print(new_test_object.test_object_type)
    print(new_test_object.test_object_name)

    _check(new_test_object.test_object_type == "id", "type mismatch")
    _check(new_test_object.test_object_name == "test_object", "name mismatch")
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)
