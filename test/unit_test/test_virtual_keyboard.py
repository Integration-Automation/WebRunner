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
        before_value = ViewportSnapshot(viewport_height=800)
        after_value = ViewportSnapshot(viewport_height=799)
        with self.assertRaises(VirtualKeyboardError):
            assert_keyboard_shrunk(
                before=before_value,
                after=after_value,
            )

    def test_bad_delta(self):
        before_value = ViewportSnapshot()
        after_value = ViewportSnapshot()
        with self.assertRaises(VirtualKeyboardError):
            assert_keyboard_shrunk(
                before=before_value, after=after_value,
                min_height_delta_px=0,
            )


class TestInset(unittest.TestCase):

    def test_pass(self):
        assert_keyboard_inset_set(ViewportSnapshot(keyboard_inset="300px"))

    def test_fail_zero(self):
        viewport_snapshot = ViewportSnapshot(keyboard_inset="0px")
        with self.assertRaises(VirtualKeyboardError):
            assert_keyboard_inset_set(viewport_snapshot)

    def test_fail_unset(self):
        viewport_snapshot = ViewportSnapshot(keyboard_inset="")
        with self.assertRaises(VirtualKeyboardError):
            assert_keyboard_inset_set(viewport_snapshot)


class TestFocused(unittest.TestCase):

    def test_pass(self):
        assert_focused_visible(
            after=ViewportSnapshot(viewport_height=500),
            focused=FocusedElementBox(selector="input", top=400, bottom=440),
        )

    def test_fail(self):
        after_value = ViewportSnapshot(viewport_height=500)
        focused_value = FocusedElementBox(selector="input",
                                      top=600, bottom=660)
        with self.assertRaises(VirtualKeyboardError):
            assert_focused_visible(
                after=after_value,
                focused=focused_value,
            )


if __name__ == "__main__":
    unittest.main()
