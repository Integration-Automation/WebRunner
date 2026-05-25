"""Unit tests for je_web_runner.utils.test_dup_dry."""
import unittest

from je_web_runner.utils.test_dup_dry.dedup import (
    DupDryError,
    DupSpec,
    assert_no_duplicates,
    find_duplicates,
    find_prefix_overlap,
)


def _act(name, **kw):
    return {"action_name": name, **kw}


class DupSpecInit(unittest.TestCase):

    def test_empty_name(self):
        with self.assertRaises(DupDryError):
            DupSpec(name="")

    def test_bad_actions(self):
        with self.assertRaises(DupDryError):
            DupSpec(name="x", actions="nope")


class TestFindDuplicates(unittest.TestCase):

    def test_basic(self):
        a = DupSpec(name="login_a", actions=[
            _act("to_url", url="/login"),
            _act("input_to_element", element_name="user"),
        ])
        b = DupSpec(name="login_b", actions=[
            _act("to_url", url="/login"),
            _act("input_to_element", element_name="user"),
        ])
        groups = find_duplicates([a, b])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].test_names, ["login_a", "login_b"])

    def test_no_dup(self):
        a = DupSpec(name="a", actions=[_act("to_url", url="/a")])
        b = DupSpec(name="b", actions=[_act("to_url", url="/b")])
        self.assertEqual(find_duplicates([a, b]), [])

    def test_bad_spec(self):
        with self.assertRaises(DupDryError):
            find_duplicates(["nope"])


class TestPrefix(unittest.TestCase):

    def test_overlap(self):
        a = DupSpec(name="a", actions=[
            _act("to_url", url="/login"),
            _act("input_to_element", element_name="user"),
            _act("input_to_element", element_name="pass"),
            _act("click_element", element_name="submit"),
            _act("assert_text", element_name="title"),
            _act("click_element", element_name="profile"),
        ])
        b = DupSpec(name="b", actions=[
            _act("to_url", url="/login"),
            _act("input_to_element", element_name="user"),
            _act("input_to_element", element_name="pass"),
            _act("click_element", element_name="submit"),
            _act("assert_text", element_name="title"),
            _act("click_element", element_name="settings"),
        ])
        out = find_prefix_overlap([a, b], min_prefix=5)
        self.assertEqual(out[0].common_prefix_len, 5)

    def test_below_threshold(self):
        a = DupSpec(name="a", actions=[_act("x"), _act("y")])
        b = DupSpec(name="b", actions=[_act("x"), _act("z")])
        self.assertEqual(find_prefix_overlap([a, b], min_prefix=5), [])

    def test_bad_min(self):
        with self.assertRaises(DupDryError):
            find_prefix_overlap([], min_prefix=0)


class TestAssert(unittest.TestCase):

    def test_pass(self):
        assert_no_duplicates([])

    def test_fail(self):
        a = DupSpec(name="a", actions=[_act("x")])
        b = DupSpec(name="b", actions=[_act("x")])
        with self.assertRaises(DupDryError):
            assert_no_duplicates(find_duplicates([a, b]))


if __name__ == "__main__":
    unittest.main()
