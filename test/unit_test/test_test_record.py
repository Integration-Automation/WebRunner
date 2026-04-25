import unittest

from je_web_runner.utils.test_record.test_record_class import TestRecord, record_action_to_list, test_record_instance


class TestTestRecord(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original_init_record = test_record_instance.init_record

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original_init_record

    def test_initial_state(self):
        record = TestRecord()
        self.assertEqual(record.test_record_list, [])
        self.assertFalse(record.init_record)

    def test_set_record_enable(self):
        record = TestRecord()
        record.set_record_enable(True)
        self.assertTrue(record.init_record)
        record.set_record_enable(False)
        self.assertFalse(record.init_record)

    def test_clean_record(self):
        record = TestRecord(init_record=True)
        record.test_record_list.append({"test": "data"})
        record.clean_record()
        self.assertEqual(record.test_record_list, [])

    def test_record_action_when_disabled(self):
        test_record_instance.init_record = False
        record_action_to_list("test_func", {"key": "value"}, None)
        self.assertEqual(len(test_record_instance.test_record_list), 0)

    def test_record_action_when_enabled(self):
        test_record_instance.init_record = True
        record_action_to_list("test_func", {"key": "value"}, None)
        self.assertEqual(len(test_record_instance.test_record_list), 1)
        record = test_record_instance.test_record_list[0]
        self.assertEqual(record["function_name"], "test_func")
        self.assertEqual(record["local_param"], {"key": "value"})
        self.assertEqual(record["program_exception"], "None")
        self.assertIn("time", record)

    def test_record_action_with_exception(self):
        test_record_instance.init_record = True
        error = ValueError("test error")
        record_action_to_list("failing_func", {"p": 1}, error)
        self.assertEqual(len(test_record_instance.test_record_list), 1)
        record = test_record_instance.test_record_list[0]
        self.assertEqual(record["function_name"], "failing_func")
        self.assertIn("ValueError", record["program_exception"])

    def test_record_action_multiple(self):
        test_record_instance.init_record = True
        record_action_to_list("func1", None, None)
        record_action_to_list("func2", None, None)
        record_action_to_list("func3", None, RuntimeError("err"))
        self.assertEqual(len(test_record_instance.test_record_list), 3)


if __name__ == "__main__":
    unittest.main()
