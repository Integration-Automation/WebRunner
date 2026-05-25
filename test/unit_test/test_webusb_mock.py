"""Unit tests for je_web_runner.utils.webusb_mock."""
import unittest

from je_web_runner.utils.webusb_mock.mock import (
    INSTALL_SCRIPT,
    OutgoingCall,
    WebusbMockError,
    assert_control_out,
    assert_transfer_out,
    build_mock_device,
    parse_outgoing,
)


class TestBuilder(unittest.TestCase):

    def test_basic(self):
        d = build_mock_device(0xabcd, 0x1234, product_name="X")
        self.assertEqual(d.product_name, "X")

    def test_bad_ids(self):
        with self.assertRaises(WebusbMockError):
            build_mock_device(-1, 0)
        with self.assertRaises(WebusbMockError):
            build_mock_device(0, 0x1FFFF)


class TestScript(unittest.TestCase):

    def test_contains_hooks(self):
        self.assertIn("navigator.usb", INSTALL_SCRIPT)
        self.assertIn("__wr_usb__", INSTALL_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        out = parse_outgoing([{"kind": "transferOut",
                               "endpoint": 1, "data": [1, 2]}])
        self.assertEqual(out[0].endpoint, 1)

    def test_bad_payload(self):
        with self.assertRaises(WebusbMockError):
            parse_outgoing("nope")

    def test_skips_non_dict(self):
        self.assertEqual(parse_outgoing(["x"]), [])


class TestTransferOut(unittest.TestCase):

    def test_pass(self):
        c = assert_transfer_out(
            [OutgoingCall(kind="transferOut", endpoint=1, data=[1, 2, 3])],
            endpoint=1, contains=[2, 3],
        )
        self.assertEqual(c.endpoint, 1)

    def test_endpoint_missing(self):
        with self.assertRaises(WebusbMockError):
            assert_transfer_out([], endpoint=1)

    def test_contains_missing(self):
        with self.assertRaises(WebusbMockError):
            assert_transfer_out(
                [OutgoingCall(kind="transferOut", endpoint=1, data=[1])],
                endpoint=1, contains=[9],
            )

    def test_no_contains(self):
        c = assert_transfer_out(
            [OutgoingCall(kind="transferOut", endpoint=2, data=[])],
            endpoint=2,
        )
        self.assertEqual(c.endpoint, 2)


class TestControlOut(unittest.TestCase):

    def test_pass(self):
        c = assert_control_out(
            [OutgoingCall(kind="controlOut", setup={"request": 5}, data=[])],
            request=5,
        )
        self.assertEqual(c.setup["request"], 5)

    def test_no_match_request(self):
        with self.assertRaises(WebusbMockError):
            assert_control_out(
                [OutgoingCall(kind="controlOut", setup={"request": 5})],
                request=9,
            )

    def test_no_control_at_all(self):
        with self.assertRaises(WebusbMockError):
            assert_control_out([])

    def test_no_request_filter(self):
        c = assert_control_out(
            [OutgoingCall(kind="controlOut", setup={}, data=[])],
        )
        self.assertEqual(c.kind, "controlOut")


if __name__ == "__main__":
    unittest.main()
