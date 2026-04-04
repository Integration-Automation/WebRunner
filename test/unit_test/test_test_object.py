import unittest

from je_web_runner.utils.test_object.test_object_class import (
    TestObject, create_test_object, get_test_object_type_list, type_list
)


class TestTestObject(unittest.TestCase):

    def test_create_test_object_with_valid_type(self):
        obj = create_test_object("id", "my_element")
        self.assertEqual(obj.test_object_type, "id")
        self.assertEqual(obj.test_object_name, "my_element")

    def test_create_test_object_various_locators(self):
        for locator in ["ID", "XPATH", "CSS_SELECTOR", "NAME", "CLASS_NAME", "TAG_NAME"]:
            obj = TestObject("value", locator)
            self.assertEqual(obj.test_object_type, locator)

    def test_create_test_object_invalid_type_raises(self):
        with self.assertRaises(TypeError):
            TestObject("value", "INVALID_LOCATOR_TYPE")

    def test_type_list_excludes_private_attributes(self):
        for attr in type_list:
            self.assertFalse(attr.startswith('_'),
                             f"type_list should not contain private attribute: {attr}")

    def test_type_list_contains_expected_locators(self):
        self.assertIn("ID", type_list)
        self.assertIn("XPATH", type_list)
        self.assertIn("CSS_SELECTOR", type_list)
        self.assertIn("NAME", type_list)

    def test_get_test_object_type_list_returns_same_list(self):
        self.assertIs(get_test_object_type_list(), type_list)


if __name__ == "__main__":
    unittest.main()
