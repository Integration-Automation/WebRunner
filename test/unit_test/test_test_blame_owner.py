"""Unit tests for je_web_runner.utils.test_blame_owner."""
import unittest

from je_web_runner.utils.test_blame_owner.owner import (
    BlameLine,
    OwnerVerdict,
    BlameOwnerError,
    assert_has_owner,
    owners_from_blame,
    owners_from_codeowners,
    parse_codeowners,
    resolve_owner,
)


CODEOWNERS = """
# top-level
* @platform
test/unit_test/payments/* @payments-team @alice
"""


class TestParseCodeowners(unittest.TestCase):

    def test_basic(self):
        rules = parse_codeowners(CODEOWNERS)
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[1].owners, ["payments-team", "alice"])

    def test_skip_comments_and_blanks(self):
        rules = parse_codeowners("# only comment\n\n   \n")
        self.assertEqual(rules, [])

    def test_bad_type(self):
        with self.assertRaises(BlameOwnerError):
            parse_codeowners(None)
  # NOSONAR python:S5655 - deliberate bad input

class TestOwnersFromCodeowners(unittest.TestCase):

    def test_specific_wins(self):
        rules = parse_codeowners(CODEOWNERS)
        owners = owners_from_codeowners(
            rules, "test/unit_test/payments/test_x.py",
        )
        self.assertEqual(owners, ["payments-team", "alice"])

    def test_fallback_to_global(self):
        rules = parse_codeowners(CODEOWNERS)
        owners = owners_from_codeowners(rules, "test/other/test_y.py")
        self.assertEqual(owners, ["platform"])

    def test_empty_path(self):
        with self.assertRaises(BlameOwnerError):
            owners_from_codeowners([], "")


class TestOwnersFromBlame(unittest.TestCase):

    def test_top3(self):
        blame = [BlameLine(author="alice")] * 5 + [BlameLine(author="bob")] * 2
        self.assertEqual(owners_from_blame(blame), ["alice", "bob"])

    def test_empty(self):
        self.assertEqual(owners_from_blame([]), [])


class TestResolveOwner(unittest.TestCase):

    def test_codeowners_wins(self):
        v = resolve_owner(
            "test/unit_test/payments/test_x.py",
            codeowners=parse_codeowners(CODEOWNERS),
            blame=[BlameLine(author="bob")],
            head_author="head",
            default="platform",
        )
        self.assertEqual(v.primary, "payments-team")
        self.assertEqual(v.source, "codeowners")

    def test_blame_when_no_codeowners(self):
        v = resolve_owner(
            "test/other/test_y.py",
            codeowners=[],
            blame=[BlameLine(author="bob")],
            head_author="head",
            default="x",
        )
        self.assertEqual(v.primary, "bob")
        self.assertEqual(v.source, "blame")

    def test_head_fallback(self):
        v = resolve_owner(
            "test/y.py", codeowners=[], blame=[], head_author="head",
            default="default",
        )
        self.assertEqual(v.primary, "head")
        self.assertEqual(v.source, "head")

    def test_default_fallback(self):
        v = resolve_owner(
            "test/y.py", codeowners=[], blame=[], head_author="",
            default="defaultuser",
        )
        self.assertEqual(v.primary, "defaultuser")

    def test_no_owner_raises(self):
        with self.assertRaises(BlameOwnerError):
            resolve_owner("test/y.py", codeowners=[], blame=[],
                          head_author="", default="")


class TestAssertHasOwner(unittest.TestCase):

    def test_pass(self):
        assert_has_owner(OwnerVerdict(primary="alice"))

    def test_fail(self):
        with self.assertRaises(BlameOwnerError):
            assert_has_owner(OwnerVerdict(primary=""))


if __name__ == "__main__":
    unittest.main()
