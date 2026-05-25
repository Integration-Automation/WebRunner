"""Unit tests for je_web_runner.utils.web_push_assert."""
import unittest

from je_web_runner.utils.web_push_assert.push import (
    INSTALL_SCRIPT,
    Notification,
    PushLog,
    Subscription,
    WebPushAssertError,
    assert_endpoint_recognised,
    assert_notification_shown,
    assert_subscribed_with_vapid,
    assert_user_visible_only,
    parse_log,
)


VAPID_PUB = "BLpzJBYDOC0FmL5HrMMUz9nLW0VVTk5pHTcQ0KdYmL9oVQyMJp"


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("pushManager", INSTALL_SCRIPT)
        self.assertIn("__wr_push__", INSTALL_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        log = parse_log({
            "subscriptions": [{"applicationServerKey": VAPID_PUB,
                               "userVisibleOnly": True,
                               "endpoint": "https://fcm.googleapis.com/x"}],
            "notifications": [{"title": "t", "body": "b"}],
        })
        self.assertEqual(log.subscriptions[0].endpoint,
                         "https://fcm.googleapis.com/x")

    def test_bad(self):
        with self.assertRaises(WebPushAssertError):
            parse_log("nope")

    def test_skip_non_dict(self):
        log = parse_log({"subscriptions": ["x"], "notifications": ["y"]})
        self.assertEqual(log.subscriptions, [])


class TestVapid(unittest.TestCase):

    def test_pass(self):
        assert_subscribed_with_vapid(
            PushLog(subscriptions=[Subscription(application_server_key=VAPID_PUB)]),
            vapid_public_key=VAPID_PUB,
        )

    def test_fail(self):
        with self.assertRaises(WebPushAssertError):
            assert_subscribed_with_vapid(
                PushLog(subscriptions=[Subscription(application_server_key="wrong")]),
                vapid_public_key=VAPID_PUB,
            )

    def test_no_sub(self):
        with self.assertRaises(WebPushAssertError):
            assert_subscribed_with_vapid(PushLog(), vapid_public_key=VAPID_PUB)

    def test_empty_key(self):
        with self.assertRaises(WebPushAssertError):
            assert_subscribed_with_vapid(PushLog(), vapid_public_key="")


class TestUserVisible(unittest.TestCase):

    def test_pass(self):
        assert_user_visible_only(PushLog(subscriptions=[
            Subscription(user_visible_only=True),
        ]))

    def test_fail(self):
        with self.assertRaises(WebPushAssertError):
            assert_user_visible_only(PushLog(subscriptions=[
                Subscription(user_visible_only=False),
            ]))


class TestEndpoint(unittest.TestCase):

    def test_pass_fcm(self):
        assert_endpoint_recognised(PushLog(subscriptions=[
            Subscription(endpoint="https://fcm.googleapis.com/fcm/send/x"),
        ]))

    def test_pass_mozilla(self):
        assert_endpoint_recognised(PushLog(subscriptions=[
            Subscription(endpoint="https://updates.push.services.mozilla.com/wpush/abc"),
        ]))

    def test_fail_unknown(self):
        with self.assertRaises(WebPushAssertError):
            assert_endpoint_recognised(PushLog(subscriptions=[
                Subscription(endpoint="https://attacker.com/x"),
            ]))

    def test_skip_empty_endpoint(self):
        assert_endpoint_recognised(PushLog(subscriptions=[
            Subscription(endpoint=""),
        ]))


class TestNotification(unittest.TestCase):

    def test_pass(self):
        n = assert_notification_shown(PushLog(notifications=[
            Notification(title="t", body="Order shipped"),
        ]), body_contains="shipped")
        self.assertEqual(n.body, "Order shipped")

    def test_no_filter(self):
        n = assert_notification_shown(PushLog(notifications=[Notification()]))
        self.assertIsNotNone(n)

    def test_no_notifications(self):
        with self.assertRaises(WebPushAssertError):
            assert_notification_shown(PushLog())

    def test_no_match(self):
        with self.assertRaises(WebPushAssertError):
            assert_notification_shown(PushLog(notifications=[
                Notification(body="x"),
            ]), body_contains="y")


if __name__ == "__main__":
    unittest.main()
