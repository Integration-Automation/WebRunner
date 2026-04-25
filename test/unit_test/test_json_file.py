import os
import tempfile
import unittest

from je_web_runner.utils.json.json_file.json_file import read_action_json, write_action_json
from je_web_runner.utils.exception.exceptions import WebRunnerJsonException


class TestJsonFile(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_write_and_read_action_json(self):
        file_path = os.path.join(self.test_dir, "test_action.json")
        data = [["WR_to_url", {"url": "https://example.com"}], ["WR_quit"]]
        write_action_json(file_path, data)
        self.assertTrue(os.path.exists(file_path))
        result = read_action_json(file_path)
        self.assertEqual(result, data)

    def test_read_nonexistent_file_raises(self):
        with self.assertRaises(WebRunnerJsonException):
            read_action_json(os.path.join(self.test_dir, "nonexistent.json"))

    def test_write_json_with_unicode(self):
        file_path = os.path.join(self.test_dir, "unicode.json")
        data = [["action", {"text": "中文測試"}]]
        write_action_json(file_path, data)
        result = read_action_json(file_path)
        self.assertEqual(result[0][1]["text"], "中文測試")

    def test_write_empty_list(self):
        file_path = os.path.join(self.test_dir, "empty.json")
        write_action_json(file_path, [])
        result = read_action_json(file_path)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
