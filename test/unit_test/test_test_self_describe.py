"""Unit tests for je_web_runner.utils.test_self_describe."""
import unittest

from je_web_runner.utils.test_self_describe.describe import (
    SelfDescribeError,
    assert_mentions,
    describe,
    summarise,
)


def _a(name, **kw):
    return {"action_name": name, **kw}


class TestSummarise(unittest.TestCase):

    def test_navigation_url(self):
        s = summarise([_a("to_url", url="https://x/")])
        self.assertEqual(s[0].phase, "Given")
        self.assertIn("https://x/", s[0].sentence)

    def test_input(self):
        s = summarise([_a("input_to_element",
                          element_name="search", input_value="foo")])
        self.assertEqual(s[0].phase, "When")
        self.assertIn("foo", s[0].sentence)
        self.assertIn("search", s[0].sentence)

    def test_click(self):
        s = summarise([_a("click_element", element_name="submit")])
        self.assertEqual(s[0].phase, "When")
        self.assertIn("submit", s[0].sentence)

    def test_assert(self):
        s = summarise([_a("assert_text", element_name="result", expected="ok")])
        self.assertEqual(s[0].phase, "Then")

    def test_wait(self):
        s = summarise([_a("wait_visible", element_name="x", timeout=10)])
        self.assertIn("up to 10s", s[0].sentence)

    def test_scroll(self):
        s = summarise([_a("scroll_to_element", element_name="x")])
        self.assertEqual(s[0].phase, "When")

    def test_back(self):
        s = summarise([_a("back")])
        self.assertIn("back", s[0].sentence)

    def test_unknown(self):
        s = summarise([_a("hover", element_name="x")])
        self.assertEqual(s[0].phase, "When")

    def test_empty(self):
        with self.assertRaises(SelfDescribeError):
            summarise([])

    def test_bad_type(self):
        with self.assertRaises(SelfDescribeError):
            summarise("nope")

    def test_non_dict_step(self):
        with self.assertRaises(SelfDescribeError):
            summarise(["nope"])


class TestDescribe(unittest.TestCase):

    def test_full_paragraph(self):
        actions = [
            _a("to_url", url="https://shop.example/"),
            _a("input_to_element", element_name="q", input_value="laptop"),
            _a("click_element", element_name="search-btn"),
            _a("assert_text", element_name="result-0", expected="laptop"),
        ]
        text = describe(actions, title="Search flow")
        self.assertIn("# Search flow", text)
        self.assertIn("Given", text)
        self.assertIn("When", text)
        self.assertIn("Then", text)
        self.assertIn("And", text)  # consecutive When → "And"

    def test_no_title(self):
        text = describe([_a("to_url", url="/")])
        self.assertFalse(text.startswith("#"))

    def test_bad_title(self):
        with self.assertRaises(SelfDescribeError):
            describe([_a("to_url", url="/")], title=123)  # NOSONAR python:S5655 - deliberate bad input


class TestAssertMentions(unittest.TestCase):

    def test_pass(self):
        assert_mentions("the user clicks submit", "submit")

    def test_fail(self):
        with self.assertRaises(SelfDescribeError):
            assert_mentions("hello", "submit")

    def test_no_needles(self):
        with self.assertRaises(SelfDescribeError):
            assert_mentions("x")

    def test_bad_type(self):
        with self.assertRaises(SelfDescribeError):
            assert_mentions(123, "x")


if __name__ == "__main__":
    unittest.main()
