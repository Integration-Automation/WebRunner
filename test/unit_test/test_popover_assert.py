"""Unit tests for je_web_runner.utils.popover_assert."""
import unittest

from je_web_runner.utils.popover_assert.popover import (
    HARVEST_SCRIPT,
    PopoverAssertError,
    PopoverKind,
    PopoverState,
    assert_closed,
    assert_invoker_link,
    assert_no_open,
    assert_only_one_modal,
    assert_open,
    parse_snapshot,
)


def _raw(id_, *, kind="dialog", open_=False, modal=False, invoker=None):
    return {"id": id_, "kind": kind, "open": open_, "modal": modal, "invoker": invoker}


class TestHarvestScript(unittest.TestCase):

    def test_script_uses_popover_open(self):
        self.assertIn(":popover-open", HARVEST_SCRIPT)
        self.assertIn("querySelectorAll", HARVEST_SCRIPT)


class TestParseSnapshot(unittest.TestCase):

    def test_basic(self):
        states = parse_snapshot([_raw("d1", open_=True, modal=True)])
        self.assertEqual(states[0].kind, PopoverKind.DIALOG)
        self.assertTrue(states[0].modal)

    def test_unknown_kind(self):
        with self.assertRaises(PopoverAssertError):
            parse_snapshot([{"kind": "weird", "open": True}])

    def test_skips_non_dict(self):
        self.assertEqual(parse_snapshot(["x", None]), [])

    def test_rejects_non_list(self):
        with self.assertRaises(PopoverAssertError):
            parse_snapshot({"x": 1})


class TestAssertOpen(unittest.TestCase):

    def test_pass(self):
        states = parse_snapshot([_raw("d", open_=True)])
        assert_open(states, id_="d")

    def test_closed_fails(self):
        states = parse_snapshot([_raw("d", open_=False)])
        with self.assertRaises(PopoverAssertError):
            assert_open(states, id_="d")

    def test_missing_fails(self):
        with self.assertRaises(PopoverAssertError):
            assert_open([], id_="missing")

    def test_empty_id(self):
        with self.assertRaises(PopoverAssertError):
            assert_open([], id_="")


class TestAssertClosed(unittest.TestCase):

    def test_pass(self):
        assert_closed(parse_snapshot([_raw("d", open_=False)]), id_="d")

    def test_open_fails(self):
        with self.assertRaises(PopoverAssertError):
            assert_closed(parse_snapshot([_raw("d", open_=True)]), id_="d")


class TestOnlyOneModal(unittest.TestCase):

    def test_zero_or_one_passes(self):
        assert_only_one_modal([])
        assert_only_one_modal(parse_snapshot([_raw("d", modal=True, open_=True)]))

    def test_two_modal_fails(self):
        states = parse_snapshot([
            _raw("a", modal=True, open_=True),
            _raw("b", modal=True, open_=True),
        ])
        with self.assertRaises(PopoverAssertError):
            assert_only_one_modal(states)


class TestInvokerLink(unittest.TestCase):

    def test_pass(self):
        states = parse_snapshot([
            _raw("menu", kind="auto", open_=True, invoker="btn1"),
        ])
        assert_invoker_link(states, popover_id="menu", invoker_id="btn1")

    def test_mismatch(self):
        states = parse_snapshot([
            _raw("menu", kind="auto", open_=True, invoker="btn2"),
        ])
        with self.assertRaises(PopoverAssertError):
            assert_invoker_link(states, popover_id="menu", invoker_id="btn1")

    def test_missing(self):
        with self.assertRaises(PopoverAssertError):
            assert_invoker_link([], popover_id="menu", invoker_id="btn1")


class TestNoOpen(unittest.TestCase):

    def test_pass(self):
        assert_no_open(parse_snapshot([_raw("d", open_=False)]))

    def test_fails(self):
        with self.assertRaises(PopoverAssertError):
            assert_no_open(parse_snapshot([_raw("d", open_=True)]))


class TestToDict(unittest.TestCase):

    def test_kind_value(self):
        s = PopoverState(kind=PopoverKind.POPOVER_AUTO, open=True, id="x")
        self.assertEqual(s.to_dict()["kind"], "auto")


if __name__ == "__main__":
    unittest.main()
