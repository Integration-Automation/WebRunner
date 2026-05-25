"""Unit tests for je_web_runner.utils.virtual_keyboard."""
import unittest

from je_web_runner.utils.virtual_keyboard.keyboard import (
    FocusedElementBox,
    HARVEST_SCRIPT,
    ViewportSnapshot,
    VirtualKeyboardError,
    assert_focused_visible,
    assert_keyboard_inset_set,
    assert_keyboard_shrunk,
    parse_snapshot,
)


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("visualViewport", HARVEST_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        snap = parse_snapshot({"viewport_height": 600, "keyboard_inset": "300px"})
        self.assertEqual(snap.viewport_height, 600)
        self.assertEqual(snap.keyboard_inset, "300px")

    def test_bad(self):
        with self.assertRaises(VirtualKeyboardError):
            parse_snapshot("nope")


class TestShrunk(unittest.TestCase):

    def test_pass(self):
        assert_keyboard_shrunk(
            before=ViewportSnapshot(viewport_height=800),
            after=ViewportSnapshot(viewport_height=500),
        )

    def test_fail_no_change(self):
        with self.assertRaises(VirtualKeyboardError):
            assert_keyboard_shrunk(
                before=ViewportSnapshot(viewport_height=800),
                after=ViewportSnapshot(viewport_height=799),
            )

    def test_bad_delta(self):
        with self.assertRaises(VirtualKeyboardError):
            assert_keyboard_shrunk(
                before=ViewportSnapshot(), after=ViewportSnapshot(),
                min_height_delta_px=0,
            )


class TestInset(unittest.TestCase):

    def test_pass(self):
        assert_keyboard_inset_set(ViewportSnapshot(keyboard_inset="300px"))

    def test_fail_zero(self):
        with self.assertRaises(VirtualKeyboardError):
            assert_keyboard_inset_set(ViewportSnapshot(keyboard_inset="0px"))

    def test_fail_unset(self):
        with self.assertRaises(VirtualKeyboardError):
            assert_keyboard_inset_set(ViewportSnapshot(keyboard_inset=""))


class TestFocused(unittest.TestCase):

    def test_pass(self):
        assert_focused_visible(
            after=ViewportSnapshot(viewport_height=500),
            focused=FocusedElementBox(selector="input", top=400, bottom=440),
        )

    def test_fail(self):
        with self.assertRaises(VirtualKeyboardError):
            assert_focused_visible(
                after=ViewportSnapshot(viewport_height=500),
                focused=FocusedElementBox(selector="input",
                                          top=600, bottom=660),
            )


if __name__ == "__main__":
    unittest.main()
