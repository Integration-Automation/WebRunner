"""Unit tests for je_web_runner.utils.notifications_audit."""
import unittest

from je_web_runner.utils.notifications_audit.audit import (
    HARVEST_SCRIPT,
    NotificationShown,
    NotificationsAuditError,
    NotificationsLog,
    PermissionRequest,
    PermissionResult,
    assert_no_prompt_before,
    assert_no_prompt_without_gesture,
    assert_no_spam_after_deny,
    assert_notification_shown,
    assert_unique_tags,
    build_install_script,
    parse_log,
)


def _payload(requests=None, notifications=None):
    return {
        "permission_requests": requests or [],
        "notifications": notifications or [],
    }


class TestScripts(unittest.TestCase):

    def test_install_script_install_guard(self):
        js = build_install_script()
        self.assertIn("__wr_notif_installed__", js)
        self.assertIn("requestPermission", js)

    def test_harvest_constant(self):
        self.assertIn("__wr_notif_log__", HARVEST_SCRIPT)


class TestParseLog(unittest.TestCase):

    def test_basic(self):
        log = parse_log(_payload(
            requests=[{"timestamp_ms": 100, "user_gesture": True,
                       "result": "granted", "page_age_ms": 100}],
            notifications=[{"timestamp_ms": 200, "title": "hi"}],
        ))
        self.assertEqual(len(log.permission_requests), 1)
        self.assertEqual(log.permission_requests[0].result, PermissionResult.GRANTED)
        self.assertEqual(log.notifications[0].title, "hi")

    def test_unknown_result_defaults_to_default(self):
        log = parse_log(_payload(
            requests=[{"timestamp_ms": 1, "user_gesture": True, "result": "weird"}],
        ))
        self.assertEqual(log.permission_requests[0].result, PermissionResult.DEFAULT)

    def test_skips_non_dict_entries(self):
        log = parse_log(_payload(
            requests=["not dict"], notifications=[None],
        ))
        self.assertEqual(log.permission_requests, [])
        self.assertEqual(log.notifications, [])

    def test_rejects_non_dict_payload(self):
        with self.assertRaises(NotificationsAuditError):
            parse_log("nope")  # type: ignore[arg-type]


class TestAssertGesture(unittest.TestCase):

    def test_pass(self):
        assert_no_prompt_without_gesture(parse_log(_payload(
            requests=[{"timestamp_ms": 1, "user_gesture": True, "result": "default"}],
        )))

    def test_fail(self):
        with self.assertRaises(NotificationsAuditError):
            assert_no_prompt_without_gesture(parse_log(_payload(
                requests=[{"timestamp_ms": 1, "user_gesture": False,
                           "result": "default", "page_age_ms": 50}],
            )))


class TestAssertNoPromptBefore(unittest.TestCase):

    def test_pass(self):
        assert_no_prompt_before(
            parse_log(_payload(
                requests=[{"timestamp_ms": 1, "user_gesture": True,
                           "result": "default", "page_age_ms": 2000}],
            )),
            min_page_age_ms=1000,
        )

    def test_fail(self):
        with self.assertRaises(NotificationsAuditError):
            assert_no_prompt_before(
                parse_log(_payload(
                    requests=[{"timestamp_ms": 1, "user_gesture": True,
                               "result": "default", "page_age_ms": 100}],
                )),
                min_page_age_ms=1000,
            )

    def test_bad_threshold(self):
        with self.assertRaises(NotificationsAuditError):
            assert_no_prompt_before(NotificationsLog(), min_page_age_ms=-1)


class TestAssertNoSpamAfterDeny(unittest.TestCase):

    def test_no_deny_no_op(self):
        assert_no_spam_after_deny(parse_log(_payload(
            notifications=[{"timestamp_ms": 1, "title": "x"}],
        )))

    def test_pass(self):
        assert_no_spam_after_deny(parse_log(_payload(
            requests=[{"timestamp_ms": 100, "user_gesture": True, "result": "denied"}],
        )))

    def test_reprompt_after_deny_fails(self):
        with self.assertRaises(NotificationsAuditError):
            assert_no_spam_after_deny(parse_log(_payload(
                requests=[
                    {"timestamp_ms": 100, "user_gesture": True, "result": "denied"},
                    {"timestamp_ms": 200, "user_gesture": True, "result": "default"},
                ],
            )))

    def test_notification_after_deny_fails(self):
        with self.assertRaises(NotificationsAuditError):
            assert_no_spam_after_deny(parse_log(_payload(
                requests=[{"timestamp_ms": 100, "user_gesture": True, "result": "denied"}],
                notifications=[{"timestamp_ms": 200, "title": "later notif"}],
            )))


class TestAssertShown(unittest.TestCase):

    def _log(self):
        return parse_log(_payload(notifications=[
            {"timestamp_ms": 1, "title": "Order #1234 shipped", "body": "Track here", "tag": "order"},
            {"timestamp_ms": 2, "title": "New message", "body": "from alice"},
        ]))

    def test_by_title(self):
        n = assert_notification_shown(self._log(), title_contains="Order")
        self.assertEqual(n.tag, "order")

    def test_by_body(self):
        n = assert_notification_shown(self._log(), body_contains="alice")
        self.assertEqual(n.title, "New message")

    def test_by_tag(self):
        n = assert_notification_shown(self._log(), tag="order")
        self.assertIn("Order", n.title)

    def test_combined(self):
        n = assert_notification_shown(
            self._log(), title_contains="Order", tag="order",
        )
        self.assertIsInstance(n, NotificationShown)

    def test_miss(self):
        with self.assertRaises(NotificationsAuditError):
            assert_notification_shown(self._log(), title_contains="missing")

    def test_no_filter(self):
        with self.assertRaises(NotificationsAuditError):
            assert_notification_shown(self._log())


class TestUniqueTags(unittest.TestCase):

    def test_pass(self):
        log = parse_log(_payload(notifications=[
            {"timestamp_ms": 1, "title": "a", "tag": "x"},
            {"timestamp_ms": 2, "title": "b", "tag": "y"},
            {"timestamp_ms": 3, "title": "c"},
        ]))
        assert_unique_tags(log)

    def test_reuse_fails(self):
        log = parse_log(_payload(notifications=[
            {"timestamp_ms": 1, "title": "a", "tag": "x"},
            {"timestamp_ms": 2, "title": "b", "tag": "x"},
        ]))
        with self.assertRaises(NotificationsAuditError):
            assert_unique_tags(log)


class TestDictRoundTrip(unittest.TestCase):

    def test_request_to_dict(self):
        req = PermissionRequest(
            timestamp_ms=1.0, user_gesture=True,
            result=PermissionResult.GRANTED, page_age_ms=2.0,
        )
        self.assertEqual(req.to_dict()["result"], "granted")


if __name__ == "__main__":
    unittest.main()
