import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.smart_wait import (
    SmartWaitError,
    wait_for_fetch_idle,
    wait_for_spa_route_stable,
    wait_until,
)


class TestWaitUntil(unittest.TestCase):

    def test_returns_when_predicate_true(self):
        wait_until(lambda: True, timeout=0.1, poll=0.01, sleep=lambda _s: None)

    def test_raises_on_timeout(self):
        with self.assertRaises(SmartWaitError):
            wait_until(lambda: False, timeout=0.05, poll=0.01, sleep=lambda _s: None)


class TestFetchIdle(unittest.TestCase):

    def test_returns_when_zero_inflight_for_quiet_window(self):
        driver = MagicMock()
        driver.execute_script.return_value = 0
        wait_for_fetch_idle(driver, quiet_for=0, timeout=0.5, poll=0.01,
                            sleep=lambda _s: None)
        # Confirm the hook installation script ran at least once
        installed = [c.args[0] for c in driver.execute_script.call_args_list]
        self.assertTrue(any("__wrFetchHook" in s for s in installed))

    def test_raises_when_never_idle(self):
        driver = MagicMock()
        driver.execute_script.return_value = 3  # always in-flight
        with self.assertRaises(SmartWaitError):
            wait_for_fetch_idle(driver, quiet_for=0.05, timeout=0.05,
                                poll=0.01, sleep=lambda _s: None)


class TestSpaRouteStable(unittest.TestCase):

    def test_returns_when_no_recent_change(self):
        driver = MagicMock()
        # last_change=0, Date.now=10000 ⇒ 10s since change
        driver.execute_script.side_effect = [
            None, None,  # hook installs
            0,           # __wrLastRouteChange
            10000,       # Date.now
        ]
        wait_for_spa_route_stable(driver, quiet_for=0.1, timeout=0.5,
                                  poll=0.01, sleep=lambda _s: None)


if __name__ == "__main__":
    unittest.main()
