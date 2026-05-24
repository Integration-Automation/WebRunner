"""Unit tests for je_web_runner.utils.file_system_access."""
import unittest

from je_web_runner.utils.file_system_access.mock import (
    FileSystemAccessError,
    HARVEST_SCRIPT,
    MockFile,
    WriteEvent,
    assert_no_writes,
    assert_wrote,
    build_install_script,
    combined_payload,
    parse_writes,
)


class TestMockFile(unittest.TestCase):

    def test_rejects_empty_name(self):
        with self.assertRaises(FileSystemAccessError):
            MockFile(name="")

    def test_rejects_non_string_contents(self):
        with self.assertRaises(FileSystemAccessError):
            MockFile(name="x", contents=123)  # type: ignore[arg-type]


class TestInstallScript(unittest.TestCase):

    def test_embeds_files(self):
        js = build_install_script([MockFile(name="hello.txt", contents="hi")])
        self.assertIn("hello.txt", js)
        self.assertIn("hi", js)
        self.assertIn("showOpenFilePicker", js)
        self.assertIn("showSaveFilePicker", js)

    def test_install_guard(self):
        self.assertIn("__wr_fsa_installed__", build_install_script())

    def test_save_suggested_name(self):
        js = build_install_script(save_suggested_name="report.pdf")
        self.assertIn("report.pdf", js)

    def test_save_default_null(self):
        js = build_install_script()
        self.assertIn("saveName = null", js)

    def test_harvest_constant(self):
        self.assertIn("__wr_fsa_writes__", HARVEST_SCRIPT)


class TestParseWrites(unittest.TestCase):

    def test_parses(self):
        writes = parse_writes([
            {"file_name": "a.txt", "sequence": 1, "data": "hello"},
            {"file_name": "a.txt", "sequence": 2, "data": " world"},
        ])
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[1].data, " world")

    def test_skips_non_dict(self):
        self.assertEqual(parse_writes(["string", None]), [])  # type: ignore[list-item]

    def test_rejects_non_list(self):
        with self.assertRaises(FileSystemAccessError):
            parse_writes({"x": 1})  # type: ignore[arg-type]

    def test_rejects_malformed(self):
        with self.assertRaises(FileSystemAccessError):
            parse_writes([{"missing_seq": True}])


class TestAssertNoWrites(unittest.TestCase):

    def test_pass(self):
        assert_no_writes([])

    def test_fail(self):
        with self.assertRaises(FileSystemAccessError):
            assert_no_writes([WriteEvent(file_name="a", sequence=1, data="x")])


class TestAssertWrote(unittest.TestCase):

    def _writes(self):
        return [
            WriteEvent(file_name="report.pdf", sequence=1, data="header"),
            WriteEvent(file_name="report.pdf", sequence=2, data="body content"),
            WriteEvent(file_name="other.txt", sequence=3, data="hello"),
        ]

    def test_by_name(self):
        w = assert_wrote(self._writes(), file_name="other.txt")
        self.assertEqual(w.data, "hello")

    def test_by_contains(self):
        w = assert_wrote(self._writes(), contains="body")
        self.assertIn("body", w.data)

    def test_both_filters(self):
        w = assert_wrote(self._writes(), file_name="report.pdf", contains="body")
        self.assertEqual(w.sequence, 2)

    def test_miss(self):
        with self.assertRaises(FileSystemAccessError):
            assert_wrote(self._writes(), file_name="missing.txt")

    def test_no_filter(self):
        with self.assertRaises(FileSystemAccessError):
            assert_wrote(self._writes())


class TestCombinedPayload(unittest.TestCase):

    def test_concatenates_in_order(self):
        writes = [
            WriteEvent(file_name="a", sequence=2, data="b"),
            WriteEvent(file_name="a", sequence=1, data="a"),
            WriteEvent(file_name="other", sequence=1, data="X"),
        ]
        self.assertEqual(combined_payload(writes, "a"), "ab")

    def test_empty_when_none(self):
        self.assertEqual(combined_payload([], "x"), "")

    def test_bad_file_name(self):
        with self.assertRaises(FileSystemAccessError):
            combined_payload([], "")


if __name__ == "__main__":
    unittest.main()
