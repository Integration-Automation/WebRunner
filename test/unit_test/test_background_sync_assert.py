"""Unit tests for je_web_runner.utils.background_sync_assert."""
import unittest

from je_web_runner.utils.background_sync_assert.sync import (
    BackgroundSyncAssertError,
    INSTALL_SCRIPT,
    SyncFire,
    SyncLog,
    assert_fired,
    assert_no_quota_exhaustion,
    assert_registered,
    assert_retry_happened,
    parse_log,
)


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("sync.register", INSTALL_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        log = parse_log({"registered": ["queue-order"],
                         "fired": [{"tag": "queue-order"}]})
        self.assertEqual(log.registered, ["queue-order"])

    def test_bad_payload(self):
        with self.assertRaises(BackgroundSyncAssertError):
            parse_log("nope")

    def test_bad_registered_type(self):
        with self.assertRaises(BackgroundSyncAssertError):
            parse_log({"registered": [123]})

    def test_skip_non_dict_fired(self):
        log = parse_log({"registered": [], "fired": ["x"]})
        self.assertEqual(log.fired, [])


class TestRegistered(unittest.TestCase):

    def test_pass(self):
        assert_registered(SyncLog(registered=["q"]), tag="q")

    def test_fail(self):
        with self.assertRaises(BackgroundSyncAssertError):
            assert_registered(SyncLog(), tag="q")

    def test_empty(self):
        with self.assertRaises(BackgroundSyncAssertError):
            assert_registered(SyncLog(), tag="")


class TestFired(unittest.TestCase):

    def test_pass(self):
        assert_fired(SyncLog(fired=[SyncFire(tag="q")]), tag="q")

    def test_count_pass(self):
        assert_fired(SyncLog(fired=[SyncFire(tag="q"), SyncFire(tag="q")]),
                    tag="q", at_least=2)

    def test_fail(self):
        with self.assertRaises(BackgroundSyncAssertError):
            assert_fired(SyncLog(), tag="q")

    def test_bad_at_least(self):
        with self.assertRaises(BackgroundSyncAssertError):
            assert_fired(SyncLog(), tag="q", at_least=0)


class TestRetry(unittest.TestCase):

    def test_pass(self):
        assert_retry_happened(
            SyncLog(fired=[SyncFire(tag="q"), SyncFire(tag="q")]), tag="q",
        )

    def test_fail(self):
        with self.assertRaises(BackgroundSyncAssertError):
            assert_retry_happened(SyncLog(fired=[SyncFire(tag="q")]), tag="q")


class TestQuota(unittest.TestCase):

    def test_pass(self):
        assert_no_quota_exhaustion(SyncLog(fired=[SyncFire(tag="q")]), tag="q")

    def test_fail(self):
        with self.assertRaises(BackgroundSyncAssertError):
            assert_no_quota_exhaustion(
                SyncLog(fired=[SyncFire(tag="q", last_chance=True)]),
                tag="q",
            )


if __name__ == "__main__":
    unittest.main()
