import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.multi_tab import (
    MultiTabError,
    TabChoreographer,
)


def _driver_with_handles(handles):
    driver = MagicMock()
    driver.window_handles = list(handles)
    driver.current_window_handle = handles[0] if handles else None
    return driver


class TestTabChoreographer(unittest.TestCase):

    def test_register_current_records_handle(self):
        driver = _driver_with_handles(["h1"])
        choreo = TabChoreographer()
        tab = choreo.register_current(driver, "primary")
        self.assertEqual(tab.handle, "h1")
        self.assertEqual(choreo.aliases(), ["primary"])

    def test_open_new_registers_and_switches(self):
        driver = _driver_with_handles(["h1"])

        def fake_new_window(_kind):
            driver.window_handles.append("h2")
            driver.current_window_handle = "h2"

        driver.switch_to.new_window.side_effect = fake_new_window
        choreo = TabChoreographer()
        choreo.register_current(driver, "primary")
        tab = choreo.open_new(driver, "side", url="https://example.com")
        self.assertEqual(tab.handle, "h2")
        driver.get.assert_called_once_with("https://example.com")

    def test_switch_to_unknown_alias_raises(self):
        driver = _driver_with_handles(["h1"])
        choreo = TabChoreographer()
        with self.assertRaises(MultiTabError):
            choreo.switch_to(driver, "ghost")

    def test_close_removes_alias(self):
        driver = _driver_with_handles(["h1", "h2"])
        choreo = TabChoreographer()
        choreo._register("primary", "h1")
        choreo._register("side", "h2")
        choreo.close(driver, "side")
        self.assertEqual(choreo.aliases(), ["primary"])

    def test_with_tab_restores_previous(self):
        driver = _driver_with_handles(["h1", "h2"])
        choreo = TabChoreographer()
        choreo._register("primary", "h1")
        choreo._register("side", "h2")
        seen = {}

        def action(_d):
            seen["handle"] = "h2"

        choreo.with_tab(driver, "side", action)
        self.assertEqual(seen["handle"], "h2")
        # Last call to switch_to.window should be back to h1
        self.assertEqual(driver.switch_to.window.call_args.args, ("h1",))

    def test_unsupported_driver_raises(self):
        choreo = TabChoreographer()
        with self.assertRaises(MultiTabError):
            choreo.register_current(object(), "x")


if __name__ == "__main__":
    unittest.main()
