"""Unit tests for je_web_runner.utils.tool_call_assert."""
import unittest

from je_web_runner.utils.tool_call_assert.tool import (
    ToolCall,
    ToolCallAssertError,
    assert_args_match_schema,
    assert_call_order,
    assert_called,
    assert_not_called,
    parse_calls,
)


class TestModel(unittest.TestCase):

    def test_empty_name(self):
        with self.assertRaises(ToolCallAssertError):
            ToolCall(name="")

    def test_bad_args(self):
        with self.assertRaises(ToolCallAssertError):
            ToolCall(name="x", arguments="nope")


class TestParse(unittest.TestCase):

    def test_basic(self):
        calls = parse_calls([{"name": "search", "arguments": {"q": "x"}}])
        self.assertEqual(calls[0].name, "search")

    def test_bad(self):
        with self.assertRaises(ToolCallAssertError):
            parse_calls("nope")

    def test_skip_non_dict(self):
        self.assertEqual(parse_calls(["x"]), [])


class TestCalled(unittest.TestCase):

    def test_exact_times(self):
        assert_called([ToolCall("a"), ToolCall("a")], name="a", times=2)

    def test_wrong_times(self):
        with self.assertRaises(ToolCallAssertError):
            assert_called([ToolCall("a")], name="a", times=2)

    def test_min(self):
        assert_called([ToolCall("a"), ToolCall("a")], name="a", min_times=1)

    def test_min_fail(self):
        with self.assertRaises(ToolCallAssertError):
            assert_called([], name="a", min_times=1)

    def test_max(self):
        assert_called([ToolCall("a")], name="a", max_times=3)

    def test_max_fail(self):
        with self.assertRaises(ToolCallAssertError):
            assert_called([ToolCall("a"), ToolCall("a")], name="a", max_times=1)

    def test_empty_name(self):
        with self.assertRaises(ToolCallAssertError):
            assert_called([], name="")

    def test_bad_times(self):
        with self.assertRaises(ToolCallAssertError):
            assert_called([], name="x", times=-1)


class TestNotCalled(unittest.TestCase):

    def test_pass(self):
        assert_not_called([ToolCall("safe")], denylist=["delete_user"])

    def test_fail(self):
        with self.assertRaises(ToolCallAssertError):
            assert_not_called([ToolCall("delete_user")],
                              denylist=["delete_user"])

    def test_empty_denylist(self):
        with self.assertRaises(ToolCallAssertError):
            assert_not_called([], denylist=[])


class TestSchema(unittest.TestCase):

    SEARCH_SCHEMA = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
            "lang": {"enum": ["en", "ja"]},
        },
        "additionalProperties": False,
    }

    def test_pass(self):
        assert_args_match_schema(
            ToolCall(name="search",
                     arguments={"query": "hi", "limit": 5, "lang": "ja"}),
            schema=self.SEARCH_SCHEMA,
        )

    def test_missing_required(self):
        with self.assertRaises(ToolCallAssertError):
            assert_args_match_schema(
                ToolCall(name="search", arguments={"limit": 5}),
                schema=self.SEARCH_SCHEMA,
            )

    def test_wrong_type(self):
        with self.assertRaises(ToolCallAssertError):
            assert_args_match_schema(
                ToolCall(name="search",
                         arguments={"query": "x", "limit": "five"}),
                schema=self.SEARCH_SCHEMA,
            )

    def test_unknown_key(self):
        with self.assertRaises(ToolCallAssertError):
            assert_args_match_schema(
                ToolCall(name="search",
                         arguments={"query": "x", "extra": 1}),
                schema=self.SEARCH_SCHEMA,
            )

    def test_enum_violation(self):
        with self.assertRaises(ToolCallAssertError):
            assert_args_match_schema(
                ToolCall(name="search",
                         arguments={"query": "x", "lang": "fr"}),
                schema=self.SEARCH_SCHEMA,
            )

    def test_bad_schema_type(self):
        with self.assertRaises(ToolCallAssertError):
            assert_args_match_schema(ToolCall(name="x"), schema="nope")


class TestOrder(unittest.TestCase):

    def test_pass(self):
        assert_call_order(
            [ToolCall("a"), ToolCall("b")], expected=["a", "b"],
        )

    def test_fail(self):
        with self.assertRaises(ToolCallAssertError):
            assert_call_order(
                [ToolCall("b"), ToolCall("a")], expected=["a", "b"],
            )


if __name__ == "__main__":
    unittest.main()
