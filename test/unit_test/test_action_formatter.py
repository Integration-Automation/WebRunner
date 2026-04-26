import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.action_formatter import (
    ActionFormatterError,
    format_actions,
    format_file,
    format_text,
)


class TestFormatActions(unittest.TestCase):

    def test_command_only(self):
        text = format_actions([["WR_quit_all"]])
        self.assertEqual(text, '[\n  ["WR_quit_all"]\n]\n')

    def test_kwargs_canonical_order(self):
        text = format_actions([
            ["WR_save_test_object", {"object_type": "ID",
                                     "test_object_name": "submit"}],
        ])
        # test_object_name should come before object_type per preferred order
        self.assertIn(
            '["WR_save_test_object", {"test_object_name": "submit", "object_type": "ID"}]',
            text,
        )

    def test_extra_kwargs_alphabetised(self):
        text = format_actions([
            ["WR_to_url", {"url": "https://x", "z_extra": 1, "a_extra": 2}],
        ])
        self.assertIn(
            '["WR_to_url", {"url": "https://x", "a_extra": 2, "z_extra": 1}]',
            text,
        )

    def test_length_three_action(self):
        text = format_actions([
            ["WR_to_url", ["https://x"], {"timeout": 30}],
        ])
        self.assertIn(
            '["WR_to_url", ["https://x"], {"timeout": 30}]',
            text,
        )

    def test_empty_list(self):
        self.assertEqual(format_actions([]), "[]\n")

    def test_invalid_action_command(self):
        with self.assertRaises(ActionFormatterError):
            format_actions([[]])

    def test_invalid_command_type(self):
        with self.assertRaises(ActionFormatterError):
            format_actions([[42]])

    def test_invalid_kwargs_type(self):
        with self.assertRaises(ActionFormatterError):
            format_actions([["WR_x", "string-not-dict"]])

    def test_invalid_indent(self):
        with self.assertRaises(ActionFormatterError):
            format_actions([["WR_quit_all"]], indent=-1)


class TestFormatText(unittest.TestCase):

    def test_round_trip(self):
        formatted = format_text('[["WR_quit_all"]]')
        self.assertEqual(formatted, '[\n  ["WR_quit_all"]\n]\n')

    def test_invalid_json_raises(self):
        with self.assertRaises(ActionFormatterError):
            format_text("not json")


class TestFormatFile(unittest.TestCase):

    def test_writes_when_changed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "actions.json"
            path.write_text('[["WR_quit_all"]]', encoding="utf-8")
            text, changed = format_file(path)
            self.assertTrue(changed)
            self.assertEqual(path.read_text(encoding="utf-8"),
                             '[\n  ["WR_quit_all"]\n]\n')
            self.assertEqual(text, '[\n  ["WR_quit_all"]\n]\n')

    def test_no_write_when_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "actions.json"
            path.write_text('[\n  ["WR_quit_all"]\n]\n', encoding="utf-8")
            text, changed = format_file(path)
            self.assertFalse(changed)
            self.assertEqual(text, '[\n  ["WR_quit_all"]\n]\n')

    def test_dry_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "actions.json"
            path.write_text('[["WR_quit_all"]]', encoding="utf-8")
            _, changed = format_file(path, write=False)
            self.assertTrue(changed)
            # Original file not rewritten
            self.assertEqual(path.read_text(encoding="utf-8"), '[["WR_quit_all"]]')

    def test_missing_file_raises(self):
        with self.assertRaises(ActionFormatterError):
            format_file("does/not/exist.json")


if __name__ == "__main__":
    unittest.main()
