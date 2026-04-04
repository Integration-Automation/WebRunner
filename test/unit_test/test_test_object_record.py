import unittest

from je_web_runner.utils.test_object.test_object_record.test_object_record_class import TestObjectRecord


class TestTestObjectRecord(unittest.TestCase):

    def setUp(self):
        self.record = TestObjectRecord()

    def test_save_and_retrieve_test_object(self):
        self.record.save_test_object("q", "NAME")
        obj = self.record.test_object_record_dict.get("q")
        self.assertIsNotNone(obj)
        self.assertEqual(obj.test_object_name, "q")
        self.assertEqual(obj.test_object_type, "NAME")

    def test_save_multiple_test_objects(self):
        self.record.save_test_object("elem1", "ID")
        self.record.save_test_object("elem2", "XPATH")
        self.assertEqual(len(self.record.test_object_record_dict), 2)

    def test_save_overwrite_existing(self):
        self.record.save_test_object("elem", "ID")
        self.record.save_test_object("elem", "NAME")
        obj = self.record.test_object_record_dict.get("elem")
        self.assertEqual(obj.test_object_type, "NAME")

    def test_clean_record(self):
        self.record.save_test_object("elem", "ID")
        self.record.clean_record()
        self.assertEqual(len(self.record.test_object_record_dict), 0)

    def test_remove_test_object(self):
        self.record.save_test_object("elem", "ID")
        removed = self.record.remove_test_object("elem")
        self.assertIsNotNone(removed)
        self.assertEqual(removed.test_object_name, "elem")
        self.assertNotIn("elem", self.record.test_object_record_dict)

    def test_remove_nonexistent_returns_false(self):
        result = self.record.remove_test_object("nonexistent")
        self.assertFalse(result)

    def test_get_nonexistent_returns_none(self):
        result = self.record.test_object_record_dict.get("nonexistent")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
