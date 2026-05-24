"""Unit tests for je_web_runner.utils.screen_reader_runner."""
import unittest

from je_web_runner.utils.screen_reader_runner.reader import (
    ScreenReaderError,
    ScreenReaderTranscript,
    Utterance,
    ViolationKind,
    assert_no_violations,
    assert_reads,
    walk_tree,
)


def _heading(level, name, children=None):
    return {"role": "heading", "level": level, "name": name, "children": children or []}


def _button(name=""):
    return {"role": "button", "name": name}


def _link(name):
    return {"role": "link", "name": name}


def _image(alt=""):
    return {"role": "image", "name": alt}


def _root(*children):
    return {"role": "WebArea", "name": "Page", "children": list(children)}


class TestWalkBasics(unittest.TestCase):

    def test_rejects_non_dict(self):
        with self.assertRaises(ScreenReaderError):
            walk_tree("not a tree")  # type: ignore[arg-type]

    def test_heading_spoken_with_level(self):
        t = walk_tree(_root(_heading(1, "Welcome")))
        self.assertTrue(any("heading level 1" in u.text for u in t.utterances))

    def test_button_spoken(self):
        t = walk_tree(_root(_button("Save")))
        self.assertTrue(any("button: Save" in u.text for u in t.utterances))

    def test_link_spoken(self):
        t = walk_tree(_root(_link("Documentation")))
        self.assertTrue(any("link: Documentation" in u.text for u in t.utterances))

    def test_image_with_alt(self):
        t = walk_tree(_root(_image("Company logo")))
        self.assertTrue(any("image: Company logo" in u.text for u in t.utterances))


class TestViolations(unittest.TestCase):

    def test_unnamed_button(self):
        t = walk_tree(_root(_button("")))
        kinds = [v.kind for v in t.violations]
        self.assertIn(ViolationKind.UNNAMED_INTERACTIVE, kinds)
        self.assertIn(ViolationKind.EMPTY_BUTTON, kinds)

    def test_generic_link_text(self):
        t = walk_tree(_root(_link("click here")))
        self.assertTrue(any(v.kind == ViolationKind.GENERIC_LINK_TEXT for v in t.violations))

    def test_descriptive_link_passes(self):
        t = walk_tree(_root(_link("Open the user guide")))
        self.assertFalse(any(v.kind == ViolationKind.GENERIC_LINK_TEXT for v in t.violations))

    def test_missing_alt(self):
        t = walk_tree(_root(_image("")))
        self.assertTrue(any(v.kind == ViolationKind.MISSING_ALT for v in t.violations))

    def test_decorative_image_no_violation(self):
        node = {"role": "image", "name": "", "decorative": True}
        t = walk_tree(_root(node))
        self.assertFalse(any(v.kind == ViolationKind.MISSING_ALT for v in t.violations))

    def test_heading_skip_detected(self):
        t = walk_tree(_root(_heading(1, "A"), _heading(3, "B")))
        self.assertTrue(any(v.kind == ViolationKind.HEADING_SKIP for v in t.violations))

    def test_heading_no_skip_with_h2_between(self):
        t = walk_tree(_root(_heading(1, "A"), _heading(2, "B"), _heading(3, "C")))
        self.assertFalse(any(v.kind == ViolationKind.HEADING_SKIP for v in t.violations))


class TestNested(unittest.TestCase):

    def test_walks_children_in_order(self):
        tree = _root(
            _heading(1, "First"),
            {"role": "navigation", "name": "Main",
             "children": [_link("Home"), _link("About")]},
        )
        t = walk_tree(tree)
        order = [u.text for u in t.utterances]
        self.assertEqual(order[0], "heading level 1: First")
        self.assertIn("navigation: Main", order)
        self.assertIn("link: Home", order)
        self.assertIn("link: About", order)

    def test_static_text(self):
        tree = _root({"role": "text", "name": "Welcome to the demo."})
        t = walk_tree(tree)
        self.assertTrue(any("Welcome to the demo" in u.text for u in t.utterances))


class TestSpeechAndAssertions(unittest.TestCase):

    def test_speech_joins(self):
        t = walk_tree(_root(_heading(1, "A"), _button("Save")))
        self.assertIn("heading level 1: A", t.speech())
        self.assertIn("button: Save", t.speech())

    def test_assert_no_violations_pass(self):
        assert_no_violations(walk_tree(_root(_heading(1, "A"), _button("Save"))))

    def test_assert_no_violations_fail(self):
        with self.assertRaises(ScreenReaderError):
            assert_no_violations(walk_tree(_root(_button(""))))

    def test_assert_reads_pass(self):
        u = assert_reads(walk_tree(_root(_button("Save"))), "Save")
        self.assertIsInstance(u, Utterance)

    def test_assert_reads_fail(self):
        with self.assertRaises(ScreenReaderError):
            assert_reads(walk_tree(_root(_button("Save"))), "Cancel")

    def test_assert_reads_empty_phrase(self):
        with self.assertRaises(ScreenReaderError):
            assert_reads(ScreenReaderTranscript(), "")

    def test_assert_no_violations_rejects_bad_arg(self):
        with self.assertRaises(ScreenReaderError):
            assert_no_violations("not a transcript")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
