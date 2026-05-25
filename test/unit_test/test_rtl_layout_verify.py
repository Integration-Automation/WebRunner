"""Unit tests for je_web_runner.utils.rtl_layout_verify."""
import unittest

from je_web_runner.utils.rtl_layout_verify.verify import (
    HARVEST_SCRIPT,
    RtlLayoutVerifyError,
    assert_bidi_isolation,
    assert_document_rtl,
    assert_logical_properties,
    assert_visual_order_reversed,
    parse_snapshot,
)


def _box(**kw):
    base = {
        "tag": "div", "text": "x",
        "left": 0, "right": 0, "top": 0, "bottom": 0,
        "direction": "rtl", "writingMode": "horizontal-tb",
        "marginLeft": "0px", "marginRight": "0px",
        "paddingLeft": "0px", "paddingRight": "0px",
        "unicodeBidi": "normal",
    }
    base.update(kw)
    return base


def _snap(document_dir="rtl", items=None):
    return {"documentDir": document_dir, "items": items or []}


class TestParse(unittest.TestCase):

    def test_script_constant(self):
        self.assertIn("getBoundingClientRect", HARVEST_SCRIPT)

    def test_basic(self):
        snap = parse_snapshot(_snap("rtl", [{
            "selector": ".x", "boxes": [_box(left=100, right=200)],
        }]))
        self.assertEqual(snap.document_dir, "rtl")
        self.assertEqual(len(snap.selectors[".x"]), 1)

    def test_skips_malformed(self):
        snap = parse_snapshot(_snap("rtl", [
            "string",
            {"selector": 1},
            {"selector": ".y", "boxes": ["str"]},
        ]))
        self.assertEqual(snap.selectors[".y"], [])

    def test_non_dict(self):
        with self.assertRaises(RtlLayoutVerifyError):
            parse_snapshot("nope")


class TestDocumentDir(unittest.TestCase):

    def test_pass(self):
        assert_document_rtl(parse_snapshot(_snap("rtl")))

    def test_fail(self):
        with self.assertRaises(RtlLayoutVerifyError):
            assert_document_rtl(parse_snapshot(_snap("ltr")))


class TestLogicalProperties(unittest.TestCase):

    def test_pass(self):
        snap = parse_snapshot(_snap("rtl", [{
            "selector": ".x",
            "boxes": [_box(marginLeft="0px", marginRight="8px")],
        }]))
        assert_logical_properties(snap, ".x")

    def test_fail_physical(self):
        snap = parse_snapshot(_snap("rtl", [{
            "selector": ".x",
            "boxes": [_box(marginLeft="8px", marginRight="0px")],
        }]))
        with self.assertRaises(RtlLayoutVerifyError):
            assert_logical_properties(snap, ".x")

    def test_unknown_selector(self):
        snap = parse_snapshot(_snap("rtl"))
        with self.assertRaises(RtlLayoutVerifyError):
            assert_logical_properties(snap, ".missing")


class TestVisualOrder(unittest.TestCase):

    def test_pass(self):
        snap = parse_snapshot(_snap("rtl", [{
            "selector": "ul li",
            "boxes": [
                _box(left=300, right=400),  # first child = rightmost
                _box(left=150, right=250),
                _box(left=0, right=100),
            ],
        }]))
        assert_visual_order_reversed(snap, "ul li")

    def test_fail(self):
        snap = parse_snapshot(_snap("rtl", [{
            "selector": "ul li",
            "boxes": [
                _box(left=0, right=100),    # first child = leftmost = wrong
                _box(left=300, right=400),
            ],
        }]))
        with self.assertRaises(RtlLayoutVerifyError):
            assert_visual_order_reversed(snap, "ul li")

    def test_need_two_siblings(self):
        snap = parse_snapshot(_snap("rtl", [{
            "selector": "x", "boxes": [_box()],
        }]))
        with self.assertRaises(RtlLayoutVerifyError):
            assert_visual_order_reversed(snap, "x")


class TestBidi(unittest.TestCase):

    def test_pass_with_isolate(self):
        snap = parse_snapshot(_snap("rtl", [{
            "selector": "p",
            "boxes": [_box(text="مرحبا John", unicodeBidi="isolate")],
        }]))
        assert_bidi_isolation(snap, "p")

    def test_pass_with_bdi(self):
        snap = parse_snapshot(_snap("rtl", [{
            "selector": "p",
            "boxes": [_box(tag="bdi", text="John")],
        }]))
        assert_bidi_isolation(snap, "p")

    def test_fail(self):
        snap = parse_snapshot(_snap("rtl", [{
            "selector": "p",
            "boxes": [_box(text="مرحبا John")],
        }]))
        with self.assertRaises(RtlLayoutVerifyError):
            assert_bidi_isolation(snap, "p")

    def test_unknown_selector(self):
        snap = parse_snapshot(_snap("rtl"))
        with self.assertRaises(RtlLayoutVerifyError):
            assert_bidi_isolation(snap, "missing")


if __name__ == "__main__":
    unittest.main()
