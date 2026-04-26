import logging
import unittest

from je_web_runner.utils.test_object.test_object_record.test_object_record_class import (
    TestObjectRecord,
)


class TestSaveTestObjectKwargs(unittest.TestCase):

    def test_unknown_kwargs_logged_as_warning(self):
        record = TestObjectRecord()
        with self.assertLogs("WEBRunner", level=logging.WARNING) as caplog:
            record.save_test_object("login", "ID", typo_field="oops", extra=1)
        self.assertTrue(
            any("ignoring unexpected kwargs" in line for line in caplog.output),
            msg=f"expected warning, got: {caplog.output}",
        )
        self.assertIn("login", record.test_object_record_dict)

    def test_no_warning_when_only_supported_kwargs(self):
        record = TestObjectRecord()
        # Capture WARNING+ records; nothing in this call should hit them.
        with self.assertNoLogs("WEBRunner", level=logging.WARNING):
            record.save_test_object("submit", "ID")


if __name__ == "__main__":
    unittest.main()
