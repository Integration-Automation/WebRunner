"""Unit tests for je_web_runner.utils.test_debt_dashboard."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from je_web_runner.utils.test_debt_dashboard.debt import (
    DebtItem,
    DebtKind,
    DebtReport,
    TestDebtDashboardError,
    assert_under_age_limit,
    parse_codeowners,
    report_markdown,
    scan_action_json,
    scan_directory,
    scan_python_file,
)

_NOW = datetime(2026, 5, 24, tzinfo=timezone.utc)


def _write(path: Path, body: str):
    path.write_text(body, encoding="utf-8")


class TestCodeowners(unittest.TestCase):

    def test_parse(self):
        idx = parse_codeowners(
            "# comment\n*  @team/all\n/test/checkout/  @team/checkout\n"
        )
        self.assertEqual(len(idx.rules), 2)

    def test_owner_for(self):
        idx = parse_codeowners(
            "* @team/all\n/test/checkout/*.py @team/checkout\n"
        )
        self.assertEqual(idx.owner_for("test/checkout/test_x.py"), "@team/checkout")
        self.assertEqual(idx.owner_for("other/x.py"), "@team/all")

    def test_double_star(self):
        idx = parse_codeowners("/test/**/auth_*.py @team/auth\n")
        self.assertEqual(idx.owner_for("test/sub/dir/auth_login.py"), "@team/auth")


class TestScanPython(unittest.TestCase):

    def test_skip_with_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_x.py"
            _write(path, '''import pytest
@pytest.mark.skip(reason="known broken")
def test_foo():
    pass
''')
            items = scan_python_file(path, now=_NOW)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].kind, DebtKind.SKIP)
            self.assertEqual(items[0].reason, "known broken")
            self.assertEqual(items[0].test_name, "test_foo")

    def test_xfail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_x.py"
            _write(path, '''import pytest
@pytest.mark.xfail(reason="server changed")
def test_bar():
    assert False
''')
            items = scan_python_file(path, now=_NOW)
            self.assertEqual(items[0].kind, DebtKind.XFAIL)
            self.assertEqual(items[0].reason, "server changed")

    def test_todo(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_x.py"
            _write(path, '''def test_baz():
    # TODO fix the assertion below
    assert True
''')
            items = scan_python_file(path, now=_NOW)
            self.assertEqual(items[0].kind, DebtKind.TODO)
            self.assertIn("fix the assertion", items[0].reason)

    def test_owner_assigned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test_x.py"
            _write(path, '''import pytest
@pytest.mark.skip(reason="x")
def test_y(): pass
''')
            owners = parse_codeowners("* @team/qa\n")
            items = scan_python_file(path, now=_NOW, owners=owners)
            self.assertEqual(items[0].owner, "@team/qa")

    def test_missing(self):
        with self.assertRaises(TestDebtDashboardError):
            scan_python_file("/no/such/file.py")


class TestScanActionJson(unittest.TestCase):

    def test_skip_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "actions.json"
            path.write_text(json.dumps([
                {"WR_to_url": ["https://x"]},
                {"_skip": True, "_reason": "until login fixed"},
            ]), encoding="utf-8")
            items = scan_action_json(path, now=_NOW)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].reason, "until login fixed")

    def test_non_list_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            path.write_text(json.dumps({"x": 1}), encoding="utf-8")
            self.assertEqual(scan_action_json(path, now=_NOW), [])

    def test_bad_json_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(scan_action_json(path, now=_NOW), [])

    def test_missing(self):
        with self.assertRaises(TestDebtDashboardError):
            scan_action_json("/no/such/file.json")


class TestScanDirectory(unittest.TestCase):

    def test_walks_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "test_a.py").write_text('''import pytest
@pytest.mark.skip(reason="x")
def test_y(): pass
''', encoding="utf-8")
            sub = Path(tmp) / "sub"
            sub.mkdir()
            (sub / "test_b.py").write_text('''def test_z():
    # FIXME later
    pass
''', encoding="utf-8")
            report = scan_directory(tmp, now=_NOW)
            self.assertGreaterEqual(len(report.items), 2)
            kinds = report.by_kind()
            self.assertIn("skip", kinds)
            self.assertIn("todo", kinds)

    def test_missing_dir(self):
        with self.assertRaises(TestDebtDashboardError):
            scan_directory("/no/such/dir")


class TestAggregates(unittest.TestCase):

    def test_by_owner(self):
        report = DebtReport(items=[
            DebtItem(kind=DebtKind.SKIP, path="a", line=1,
                     test_name=None, reason="x", age_days=1,
                     owner="@team/a"),
            DebtItem(kind=DebtKind.SKIP, path="b", line=1,
                     test_name=None, reason="x", age_days=1),
        ])
        owners = report.by_owner()
        self.assertEqual(owners["@team/a"], 1)
        self.assertEqual(owners["(unowned)"], 1)

    def test_older_than(self):
        report = DebtReport(items=[
            DebtItem(kind=DebtKind.SKIP, path="a", line=1,
                     test_name=None, reason="x", age_days=10),
            DebtItem(kind=DebtKind.SKIP, path="b", line=1,
                     test_name=None, reason="x", age_days=100),
        ])
        self.assertEqual(len(report.older_than(50)), 1)


class TestAssertions(unittest.TestCase):

    def test_assert_under_age_pass(self):
        report = DebtReport(items=[DebtItem(
            kind=DebtKind.SKIP, path="x", line=1, test_name=None,
            reason="", age_days=1,
        )])
        assert_under_age_limit(report, max_days=10)

    def test_assert_under_age_fail(self):
        report = DebtReport(items=[DebtItem(
            kind=DebtKind.SKIP, path="x", line=1, test_name=None,
            reason="", age_days=100,
        )])
        with self.assertRaises(TestDebtDashboardError):
            assert_under_age_limit(report, max_days=10)

    def test_assert_under_age_bad(self):
        with self.assertRaises(TestDebtDashboardError):
            assert_under_age_limit(DebtReport(), max_days=-1)


class TestMarkdown(unittest.TestCase):

    def test_renders(self):
        report = DebtReport(items=[DebtItem(
            kind=DebtKind.SKIP, path="x", line=1, test_name=None,
            reason="", age_days=1,
        )])
        md = report_markdown(report)
        self.assertIn("Test debt", md)
        self.assertIn("skip", md)

    def test_rejects_non_report(self):
        with self.assertRaises(TestDebtDashboardError):
            report_markdown("nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
