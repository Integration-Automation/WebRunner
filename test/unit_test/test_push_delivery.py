"""Unit tests for je_web_runner.utils.push_delivery."""
import unittest

from je_web_runner.utils.push_delivery.delivery import (
    PushDeliveryError,
    assert_apns_payload,
    assert_collapse_intent,
    assert_fcm_payload,
)


def _good_fcm():
    return {
        "message": {
            "token": "device-token",
            "notification": {"title": "T", "body": "B"},
            "android": {"ttl": "3600s"},
        },
    }


def _good_apns():
    return {
        "aps": {"alert": {"title": "T", "body": "B"}, "badge": 1},
    }


class TestFcm(unittest.TestCase):

    def test_pass(self):
        assert_fcm_payload(_good_fcm())

    def test_no_message(self):
        with self.assertRaises(PushDeliveryError):
            assert_fcm_payload({})

    def test_no_target(self):
        with self.assertRaises(PushDeliveryError):
            assert_fcm_payload({"message": {"notification": {}}})

    def test_too_large(self):
        big = _good_fcm()
        big["message"]["notification"]["body"] = "x" * 5000
        with self.assertRaises(PushDeliveryError):
            assert_fcm_payload(big)

    def test_pii_in_body(self):
        bad = _good_fcm()
        bad["message"]["notification"]["body"] = "Your card 4111 1111 1111 1111 expired"
        with self.assertRaises(PushDeliveryError):
            assert_fcm_payload(bad)

    def test_bad_ttl(self):
        bad = _good_fcm()
        bad["message"]["android"]["ttl"] = "0s"
        with self.assertRaises(PushDeliveryError):
            assert_fcm_payload(bad)

    def test_ttl_not_seconds(self):
        bad = _good_fcm()
        bad["message"]["android"]["ttl"] = "60"
        with self.assertRaises(PushDeliveryError):
            assert_fcm_payload(bad)

    def test_bad_payload(self):
        with self.assertRaises(PushDeliveryError):
            assert_fcm_payload("nope")


class TestApns(unittest.TestCase):

    def test_pass(self):
        assert_apns_payload(_good_apns())

    def test_missing_aps(self):
        with self.assertRaises(PushDeliveryError):
            assert_apns_payload({})

    def test_empty_aps(self):
        with self.assertRaises(PushDeliveryError):
            assert_apns_payload({"aps": {}})

    def test_pii_in_alert(self):
        bad = _good_apns()
        bad["aps"]["alert"]["title"] = "user@example.com order ready"
        with self.assertRaises(PushDeliveryError):
            assert_apns_payload(bad)

    def test_too_large(self):
        big = _good_apns()
        big["aps"]["alert"]["body"] = "x" * (5 * 1024 + 100)
        with self.assertRaises(PushDeliveryError):
            assert_apns_payload(big)


class TestCollapse(unittest.TestCase):

    def test_fcm_pass(self):
        p = _good_fcm()
        p["message"]["android"]["collapse_key"] = "chat:42"
        assert_collapse_intent(p)

    def test_fcm_missing(self):
        with self.assertRaises(PushDeliveryError):
            assert_collapse_intent(_good_fcm())

    def test_apns_pass(self):
        p = _good_apns()
        p["_apns_headers"] = {"apns-collapse-id": "chat:42"}
        assert_collapse_intent(p)

    def test_apns_missing(self):
        with self.assertRaises(PushDeliveryError):
            assert_collapse_intent(_good_apns())


if __name__ == "__main__":
    unittest.main()
