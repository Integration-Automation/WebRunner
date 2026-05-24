"""Unit tests for je_web_runner.utils.test_owners_map."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.test_owners_map.owners import (
    CodeownersRule,
    OwnerAudit,
    OwnersFile,
    OwnersMap,
    TestOwnersMapError,
    assert_no_unowned,
    audit_markdown,
    audit_unowned,
    load_codeowners_file,
    load_overrides,
    parse_codeowners,
)


_CODEOWNERS_TEXT = """\
# Global default
*                            @team/all
# Test directories
/test/checkout/              @team/checkout
/test/profile/*.json         @team/profile
/test/auth/**/*.py           @team/security
"""


class TestParseCodeowners(unittest.TestCase):

    def test_parses_lines(self):
        owners = parse_codeowners(_CODEOWNERS_TEXT)
        self.assertEqual(len(owners.rules), 4)

    def test_skips_comments_and_blank(self):
        text = "# only comments\n\n  \n"
        self.assertEqual(parse_codeowners(text).rules, [])

    def test_inline_comments_stripped(self):
        owners = parse_codeowners("/foo @team/foo # legacy\n")
        self.assertEqual(owners.rules[0].owners, ["@team/foo"])

    def test_skips_short_lines(self):
        # pattern without owner is ignored
        self.assertEqual(parse_codeowners("/lonely\n").rules, [])

    def test_rejects_non_string(self):
        with self.assertRaises(TestOwnersMapError):
            parse_codeowners(123)  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test


class TestLookup(unittest.TestCase):

    def setUp(self):
        self.owners = parse_codeowners(_CODEOWNERS_TEXT)

    def test_default(self):
        self.assertEqual(self.owners.lookup("other/foo.py"), ["@team/all"])

    def test_dir_match(self):
        self.assertEqual(
            self.owners.lookup("test/checkout/sub/login.py"),
            ["@team/checkout"],
        )

    def test_glob_with_extension(self):
        self.assertEqual(
            self.owners.lookup("test/profile/edit.json"),
            ["@team/profile"],
        )

    def test_double_star(self):
        self.assertEqual(
            self.owners.lookup("test/auth/sub/login.py"),
            ["@team/security"],
        )

    def test_last_match_wins(self):
        text = "* @a\n/test/x.py @b\n"
        owners = parse_codeowners(text)
        self.assertEqual(owners.lookup("test/x.py"), ["@b"])

    def test_rejects_empty_path(self):
        with self.assertRaises(TestOwnersMapError):
            self.owners.lookup("")


class TestLoadCodeownersFile(unittest.TestCase):

    def test_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CODEOWNERS"
            path.write_text(_CODEOWNERS_TEXT, encoding="utf-8")
            owners = load_codeowners_file(path)
            self.assertEqual(len(owners.rules), 4)

    def test_missing(self):
        with self.assertRaises(TestOwnersMapError):
            load_codeowners_file("/no/such/file")


class TestOverrides(unittest.TestCase):

    def test_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "o.json"
            path.write_text(json.dumps({
                "test/checkout/login.py": ["@team/auth"],
            }), encoding="utf-8")
            overrides = load_overrides(path)
            self.assertEqual(overrides["test/checkout/login.py"], ["@team/auth"])

    def test_missing(self):
        with self.assertRaises(TestOwnersMapError):
            load_overrides("/no/such/file.json")

    def test_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "o.json"
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(TestOwnersMapError):
                load_overrides(path)

    def test_non_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "o.json"
            path.write_text(json.dumps([1, 2]), encoding="utf-8")
            with self.assertRaises(TestOwnersMapError):
                load_overrides(path)

    def test_bad_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "o.json"
            path.write_text(json.dumps({"x": "not a list"}), encoding="utf-8")
            with self.assertRaises(TestOwnersMapError):
                load_overrides(path)


class TestOwnersMap(unittest.TestCase):

    def _map(self, overrides=None):
        return OwnersMap(
            codeowners=parse_codeowners(_CODEOWNERS_TEXT),
            overrides=overrides or {},
        )

    def test_codeowners_path(self):
        self.assertEqual(
            self._map().owners_for("test/checkout/login.py"),
            ["@team/checkout"],
        )

    def test_override_wins(self):
        m = self._map({"test/checkout/login.py": ["@team/auth-override"]})
        self.assertEqual(
            m.owners_for("test/checkout/login.py"),
            ["@team/auth-override"],
        )

    def test_no_match_returns_default(self):
        self.assertEqual(
            self._map().owners_for("anywhere/else.py"),
            ["@team/all"],
        )

    def test_empty_test_id_rejected(self):
        with self.assertRaises(TestOwnersMapError):
            self._map().owners_for("")


class TestAudit(unittest.TestCase):

    def test_counts(self):
        m = OwnersMap(codeowners=parse_codeowners(_CODEOWNERS_TEXT))
        audit = audit_unowned(
            ["test/checkout/login.py", "test/auth/sub/login.py",
             "other/foo.py"],
            m,
        )
        self.assertEqual(audit.total_tests, 3)
        self.assertEqual(audit.unowned, [])
        self.assertEqual(audit.by_owner["@team/checkout"], 1)
        self.assertEqual(audit.by_owner["@team/security"], 1)

    def test_unowned_detected(self):
        owners = OwnersFile(rules=[
            CodeownersRule(pattern="/test/owned/", owners=["@team/x"]),
        ])
        audit = audit_unowned(
            ["test/owned/a.py", "test/orphan/b.py"],
            OwnersMap(codeowners=owners),
        )
        self.assertEqual(audit.unowned, ["test/orphan/b.py"])

    def test_rejects_non_map(self):
        with self.assertRaises(TestOwnersMapError):
            audit_unowned([], "nope")  # type: ignore[arg-type]


class TestAssertions(unittest.TestCase):

    def test_pass(self):
        assert_no_unowned(OwnerAudit(total_tests=1))

    def test_fail(self):
        audit = OwnerAudit(total_tests=2, unowned=["a", "b"])
        with self.assertRaises(TestOwnersMapError):
            assert_no_unowned(audit)

    def test_rejects_non_audit(self):
        with self.assertRaises(TestOwnersMapError):
            assert_no_unowned("nope")  # type: ignore[arg-type]


class TestMarkdown(unittest.TestCase):

    def test_renders(self):
        audit = OwnerAudit(
            total_tests=3, unowned=["a"], by_owner={"@team/x": 2, "@team/y": 1},
        )
        md = audit_markdown(audit)
        self.assertIn("unowned: **1**", md)
        self.assertIn("@team/x", md)

    def test_bad_top_owners(self):
        with self.assertRaises(TestOwnersMapError):
            audit_markdown(OwnerAudit(total_tests=0), top_owners=-1)

    def test_rejects_non_audit(self):
        with self.assertRaises(TestOwnersMapError):
            audit_markdown("nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
