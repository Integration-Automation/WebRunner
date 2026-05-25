"""Unit tests for je_web_runner.utils.webserial_mock."""
import unittest

from je_web_runner.utils.webserial_mock.mock import (
    INSTALL_SCRIPT,
    WebserialMockError,
    assert_lines_written,
    build_mock_port,
    encode_lines,
    parse_outbound,
)


class TestBuilder(unittest.TestCase):

    def test_basic(self):
        p = build_mock_port(vendor_id=0x10c4)
        self.assertEqual(p.vendor_id, 0x10c4)

    def test_bad_id(self):
        with self.assertRaises(WebserialMockError):
            build_mock_port(vendor_id=-1)


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("navigator.serial", INSTALL_SCRIPT)
        self.assertIn("__wr_serial__", INSTALL_SCRIPT)


class TestEncode(unittest.TestCase):

    def test_basic(self):
        out = encode_lines(["hi", "ok"])
        self.assertEqual(bytes(out).decode("utf-8"), "hi\nok\n")

    def test_crlf(self):
        out = encode_lines(["x"], newline="\r\n")
        self.assertEqual(bytes(out).decode("utf-8"), "x\r\n")

    def test_bad_lines(self):
        with self.assertRaises(WebserialMockError):
            encode_lines("nope")

    def test_bad_newline(self):
        with self.assertRaises(WebserialMockError):
            encode_lines(["x"], newline=123)  # NOSONAR python:S5655 - deliberate bad input

    def test_non_string_line(self):
        with self.assertRaises(WebserialMockError):
            encode_lines([123])


class TestParseOutbound(unittest.TestCase):

    def test_basic(self):
        out = parse_outbound([[104, 105], [10]])
        self.assertEqual(out, [b"hi", b"\n"])

    def test_skip_non_list(self):
        self.assertEqual(parse_outbound(["nope"]), [])

    def test_bad(self):
        with self.assertRaises(WebserialMockError):
            parse_outbound("nope")


class TestAssertLines(unittest.TestCase):

    def test_pass(self):
        assert_lines_written([b"hi\nok\n"], expected=["hi", "ok"])

    def test_chunked(self):
        assert_lines_written([b"hi\n", b"ok\n"], expected=["hi", "ok"])

    def test_fail(self):
        with self.assertRaises(WebserialMockError):
            assert_lines_written([b"hi\n"], expected=["ok"])


if __name__ == "__main__":
    unittest.main()
