import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.browser_pool import (
    BrowserPool,
    BrowserPoolError,
)


class TestBrowserPool(unittest.TestCase):

    def test_invalid_size_raises(self):
        with self.assertRaises(BrowserPoolError):
            BrowserPool(factory=lambda: object(), size=0)

    def test_invalid_max_uses_raises(self):
        with self.assertRaises(BrowserPoolError):
            BrowserPool(factory=lambda: object(), max_uses=0)

    def test_warm_creates_size_sessions(self):
        factory = MagicMock(side_effect=lambda: object())
        pool = BrowserPool(factory=factory, size=3)
        pool.warm()
        self.assertEqual(pool.tracked_count, 3)
        self.assertEqual(factory.call_count, 3)

    def test_checkout_reuses_warm_sessions(self):
        factory = MagicMock(side_effect=lambda: object())
        pool = BrowserPool(factory=factory, size=2)
        pool.warm()
        s1 = pool.checkout(timeout=0.1)
        s2 = pool.checkout(timeout=0.1)
        # Already warmed; no extra factory calls
        self.assertEqual(factory.call_count, 2)
        self.assertNotEqual(s1.session_id, s2.session_id)

    def test_checkin_returns_to_pool(self):
        pool = BrowserPool(factory=lambda: object(), size=1)
        pool.warm()
        sess = pool.checkout(timeout=0.1)
        pool.checkin(sess)
        sess2 = pool.checkout(timeout=0.1)
        self.assertEqual(sess2.session_id, sess.session_id)

    def test_max_uses_recycles(self):
        destructor = MagicMock()
        pool = BrowserPool(
            factory=lambda: object(),
            destructor=destructor,
            size=1,
            max_uses=1,
        )
        pool.warm()
        sess = pool.checkout(timeout=0.1)
        pool.checkin(sess)
        # uses now == 1; pool destroyed it; next checkout spawns fresh
        sess2 = pool.checkout(timeout=0.1)
        self.assertNotEqual(sess.session_id, sess2.session_id)
        destructor.assert_called_once_with(sess.instance)

    def test_unhealthy_session_recycled(self):
        destructor = MagicMock()
        check_count = {"n": 0}

        def health(_instance):
            check_count["n"] += 1
            return check_count["n"] != 2  # second check fails

        pool = BrowserPool(
            factory=lambda: object(),
            destructor=destructor,
            health_check=health,
            size=2,
        )
        pool.warm()
        sess1 = pool.checkout(timeout=0.1)
        sess2 = pool.checkout(timeout=0.1)
        # The second session fails health check on checkout and is recycled,
        # then a fresh one is spawned in its place.
        self.assertNotEqual(sess1.session_id, sess2.session_id)
        destructor.assert_called()  # destroyed at least once

    def test_factory_failure_raises(self):
        def failing():
            raise RuntimeError("no driver")

        pool = BrowserPool(factory=failing, size=1)
        with self.assertRaises(BrowserPoolError):
            pool.checkout(timeout=0.1)

    def test_context_manager_releases(self):
        pool = BrowserPool(factory=lambda: object(), size=1)
        pool.warm()
        with pool.session(timeout=0.1) as sess:
            sid = sess.session_id
        # checking in puts it back; second checkout returns the same
        with pool.session(timeout=0.1) as sess2:
            self.assertEqual(sess2.session_id, sid)

    def test_close_destroys_all(self):
        destructor = MagicMock()
        pool = BrowserPool(factory=lambda: object(), destructor=destructor, size=2)
        pool.warm()
        pool.close()
        self.assertEqual(destructor.call_count, 2)
        with self.assertRaises(BrowserPoolError):
            pool.checkout(timeout=0.1)


if __name__ == "__main__":
    unittest.main()
