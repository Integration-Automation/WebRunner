"""Unit tests for je_web_runner.utils.webhid_mock."""
import unittest

from je_web_runner.utils.webhid_mock.mock import (
    INSTALL_SCRIPT,
    OutgoingReport,
    WebhidMockError,
    assert_output_reports,
    build_input_report,
    build_mock_device,
    parse_outgoing,
)


class TestBuilders(unittest.TestCase):

    def test_device(self):
        d = build_mock_device(0x1234, 0x5678, "Pad")
        self.assertEqual(d.vendor_id, 0x1234)

    def test_device_bad_ids(self):
        with self.assertRaises(WebhidMockError):
            build_mock_device(-1, 0)
        with self.assertRaises(WebhidMockError):
            build_mock_device(0, 0x1FFFF)

    def test_input_report(self):
        r = build_input_report(2, [1, 2, 3])
        self.assertEqual(r["report_id"], 2)

    def test_input_report_bad_id(self):
        with self.assertRaises(WebhidMockError):
            build_input_report(999, [])

    def test_input_report_bad_data(self):
        with self.assertRaises(WebhidMockError):
            build_input_report(0, "nope")
        with self.assertRaises(WebhidMockError):
            build_input_report(0, [999])


class TestScript(unittest.TestCase):

    def test_contains_hooks(self):
        self.assertIn("navigator.hid", INSTALL_SCRIPT)
        self.assertIn("__wr_hid__", INSTALL_SCRIPT)


class TestParseOutgoing(unittest.TestCase):

    def test_basic(self):
        out = parse_outgoing([{"reportId": 1, "data": [10, 20]}])
        self.assertEqual(out[0].data, [10, 20])

    def test_skip_non_dict(self):
        self.assertEqual(parse_outgoing(["x"]), [])

    def test_bad_payload(self):
        with self.assertRaises(WebhidMockError):
            parse_outgoing("nope")


class TestAssert(unittest.TestCase):

    def test_count_pass(self):
        assert_output_reports([OutgoingReport(report_id=0, data=[])],
                              expected_count=1)

    def test_count_fail(self):
        with self.assertRaises(WebhidMockError):
            assert_output_reports([], expected_count=1)

    def test_contains_pass(self):
        assert_output_reports(
            [OutgoingReport(report_id=0, data=[1, 2, 3, 4])],
            contains=[2, 3],
        )

    def test_contains_fail(self):
        with self.assertRaises(WebhidMockError):
            assert_output_reports(
                [OutgoingReport(report_id=0, data=[1, 2, 3])],
                contains=[9, 9],
            )


if __name__ == "__main__":
    unittest.main()
