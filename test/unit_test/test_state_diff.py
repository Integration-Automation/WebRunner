import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.state_diff import (
    BrowserStateSnapshot,
    StateDiffError,
    capture_state,
    diff_states,
)
from je_web_runner.utils.state_diff.diff import assert_no_state_change


class TestDiffStates(unittest.TestCase):

    def test_added_removed_changed(self):
        before = BrowserStateSnapshot(
            cookies={"sid": {"name": "sid", "value": "abc"}},
            local_storage={"a": "1"},
        )
        after = BrowserStateSnapshot(
            cookies={"sid": {"name": "sid", "value": "xyz"}},
            local_storage={"a": "1", "b": "2"},
            session_storage={"s": "9"},
        )
        diff = diff_states(before, after)
        self.assertEqual(diff.cookies.changed, {
            "sid": (
                {"name": "sid", "value": "abc"},
                {"name": "sid", "value": "xyz"},
            ),
        })
        self.assertEqual(diff.local_storage.added, {"b": "2"})
        self.assertEqual(diff.session_storage.added, {"s": "9"})
        self.assertTrue(diff.has_changes)

    def test_no_changes(self):
        snap = BrowserStateSnapshot(local_storage={"a": "1"})
        diff = diff_states(snap, snap)
        self.assertFalse(diff.has_changes)

    def test_invalid_input(self):
        with self.assertRaises(StateDiffError):
            diff_states("not a snapshot", BrowserStateSnapshot())  # type: ignore[arg-type]


class TestCaptureState(unittest.TestCase):

    def test_selenium_path(self):
        driver = MagicMock()
        driver.get_cookies.return_value = [
            {"name": "sid", "value": "abc"},
        ]
        driver.execute_script.side_effect = [
            {"a": "1"},
            {"b": "2"},
        ]
        snap = capture_state(driver)
        self.assertEqual(snap.cookies["sid"]["value"], "abc")
        self.assertEqual(snap.local_storage["a"], "1")
        self.assertEqual(snap.session_storage["b"], "2")

    def test_playwright_path(self):
        page = MagicMock(spec=["context", "evaluate"])
        page.context = MagicMock()
        page.context.cookies.return_value = [{"name": "sid", "value": "x"}]
        page.evaluate.side_effect = [{"a": "1"}, {}]
        snap = capture_state(page)
        self.assertEqual(snap.cookies["sid"]["value"], "x")
        self.assertEqual(snap.local_storage["a"], "1")

    def test_unsupported_driver(self):
        with self.assertRaises(StateDiffError):
            capture_state(object())

    def test_invalid_storage_payload(self):
        driver = MagicMock()
        driver.get_cookies.return_value = []
        driver.execute_script.side_effect = ["not-a-dict", {}]
        with self.assertRaises(StateDiffError):
            capture_state(driver)


class TestAssertNoStateChange(unittest.TestCase):

    def test_passes_clean(self):
        snap = BrowserStateSnapshot()
        assert_no_state_change(diff_states(snap, snap))

    def test_raises_on_diff(self):
        before = BrowserStateSnapshot()
        after = BrowserStateSnapshot(local_storage={"a": "1"})
        diff = diff_states(before, after)
        with self.assertRaises(StateDiffError):
            assert_no_state_change(diff)

    def test_allow_keys_skips(self):
        before = BrowserStateSnapshot()
        after = BrowserStateSnapshot(local_storage={"a": "1"})
        diff = diff_states(before, after)
        assert_no_state_change(diff, allow_keys=["a"])


if __name__ == "__main__":
    unittest.main()
