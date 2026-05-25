"""Unit tests for je_web_runner.utils.wake_lock_assert."""
import unittest

from je_web_runner.utils.wake_lock_assert.lock import (
    INSTALL_SCRIPT,
    WakeLockAssertError,
    WakeLockEvent,
    WakeLockLog,
    assert_acquired,
    assert_no_leak,
    assert_re_acquired_after_visibility,
    assert_released_by_app,
    parse_log,
)


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("navigator.wakeLock", INSTALL_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        log = parse_log([
            {"kind": "acquire"},
            {"kind": "release", "by": "app"},
        ])
        self.assertEqual(log.acquired_count, 1)
        self.assertEqual(log.released_count, 1)

    def test_bad_payload(self):
        with self.assertRaises(WakeLockAssertError):
            parse_log("nope")

    def test_skip_bad_kind(self):
        log = parse_log([{"kind": "weird"}])
        self.assertEqual(len(log.events), 0)

    def test_skip_non_dict(self):
        log = parse_log(["x"])
        self.assertEqual(len(log.events), 0)


class TestAcquired(unittest.TestCase):

    def test_pass(self):
        assert_acquired(WakeLockLog(events=[WakeLockEvent(kind="acquire")]))

    def test_fail(self):
        with self.assertRaises(WakeLockAssertError):
            assert_acquired(WakeLockLog())


class TestNoLeak(unittest.TestCase):

    def test_pass(self):
        assert_no_leak(WakeLockLog(events=[
            WakeLockEvent(kind="acquire"),
            WakeLockEvent(kind="release", by="app"),
        ]))

    def test_fail(self):
        with self.assertRaises(WakeLockAssertError):
            assert_no_leak(WakeLockLog(events=[
                WakeLockEvent(kind="acquire"),
            ]))


class TestReleasedByApp(unittest.TestCase):

    def test_pass(self):
        assert_released_by_app(WakeLockLog(events=[
            WakeLockEvent(kind="release", by="app"),
        ]))

    def test_fail(self):
        with self.assertRaises(WakeLockAssertError):
            assert_released_by_app(WakeLockLog(events=[
                WakeLockEvent(kind="release", by="os"),
            ]))


class TestReAcquire(unittest.TestCase):

    def test_pass(self):
        assert_re_acquired_after_visibility(WakeLockLog(events=[
            WakeLockEvent(kind="acquire"),
            WakeLockEvent(kind="release", by="os"),
            WakeLockEvent(kind="acquire"),
        ]))

    def test_skip_no_os_release(self):
        assert_re_acquired_after_visibility(WakeLockLog(events=[
            WakeLockEvent(kind="acquire"),
            WakeLockEvent(kind="release", by="app"),
        ]))

    def test_fail(self):
        with self.assertRaises(WakeLockAssertError):
            assert_re_acquired_after_visibility(WakeLockLog(events=[
                WakeLockEvent(kind="acquire"),
                WakeLockEvent(kind="release", by="os"),
            ]))


if __name__ == "__main__":
    unittest.main()
