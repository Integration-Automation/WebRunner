import os
import tempfile
import unittest

from je_web_runner.utils.throttler import (
    FileSemaphore,
    ServiceThrottler,
    ThrottlerError,
    throttle,
)
from je_web_runner.utils.throttler.throttler import configure_global


class TestFileSemaphore(unittest.TestCase):

    def test_acquire_within_capacity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sem = FileSemaphore(name="api", capacity=2, base_dir=tmpdir)
            a = sem.acquire(timeout=0.1)
            b = sem.acquire(timeout=0.1)
            self.assertNotEqual(a, b)
            self.assertTrue(a.exists())
            self.assertTrue(b.exists())

    def test_acquire_blocks_when_full(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sem = FileSemaphore(name="api", capacity=1, base_dir=tmpdir,
                                stale_after=0)
            sem.acquire(timeout=0.1)
            with self.assertRaises(ThrottlerError):
                sem.acquire(timeout=0.05, poll=0.01)

    def test_release_makes_slot_available(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sem = FileSemaphore(name="api", capacity=1, base_dir=tmpdir,
                                stale_after=0)
            slot = sem.acquire(timeout=0.1)
            sem.release(slot)
            self.assertFalse(slot.exists())
            again = sem.acquire(timeout=0.1)
            self.assertTrue(again.exists())


class TestThrottleContextManager(unittest.TestCase):

    def test_release_on_exit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            configure_global(
                "svc", capacity=1, base_dir=tmpdir, stale_after=0
            )
            with throttle("svc", timeout=0.1) as slot:
                self.assertTrue(slot.exists())
            self.assertFalse(slot.exists())

    def test_unconfigured_service_raises(self):
        throttler = ServiceThrottler(base_dir=os.getcwd())
        with self.assertRaises(ThrottlerError):
            throttler.get("nope")


if __name__ == "__main__":
    unittest.main()
