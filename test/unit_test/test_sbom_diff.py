"""Unit tests for je_web_runner.utils.sbom_diff."""
import unittest

from je_web_runner.utils.sbom_diff.diff import (
    SbomDiffError,
    SbomReport,
    VersionChange,
    assert_no_disallowed_licenses,
    assert_no_new_vulnerable,
    diff_sboms,
    report_markdown,
)


def _component(name, version, licenses=None, purl=""):
    return {
        "name": name,
        "version": version,
        "purl": purl,
        "licenses": [{"license": {"id": l}} for l in (licenses or [])],
    }


def _sbom(*components, vulnerabilities=None):
    s = {"components": list(components)}
    if vulnerabilities is not None:
        s["vulnerabilities"] = vulnerabilities
    return s


class TestDiff(unittest.TestCase):

    def test_added_and_removed(self):
        base = _sbom(_component("a", "1.0.0"), _component("b", "1.0.0"))
        head = _sbom(_component("a", "1.0.0"), _component("c", "1.0.0"))
        report = diff_sboms(base, head)
        self.assertEqual([c.name for c in report.added], ["c"])
        self.assertEqual([c.name for c in report.removed], ["b"])

    def test_upgrade(self):
        base = _sbom(_component("lib", "1.0.0"))
        head = _sbom(_component("lib", "1.2.0"))
        report = diff_sboms(base, head)
        self.assertEqual(len(report.upgraded), 1)
        self.assertEqual(report.upgraded[0].head_version, "1.2.0")

    def test_downgrade(self):
        base = _sbom(_component("lib", "2.0.0"))
        head = _sbom(_component("lib", "1.0.0"))
        report = diff_sboms(base, head)
        self.assertEqual(len(report.downgraded), 1)

    def test_unknown_version_order_classified_as_upgrade(self):
        base = _sbom(_component("lib", "main"))
        head = _sbom(_component("lib", "release"))
        report = diff_sboms(base, head)
        self.assertEqual(len(report.upgraded), 1)

    def test_new_license(self):
        base = _sbom(_component("a", "1", licenses=["MIT"]))
        head = _sbom(_component("a", "1", licenses=["MIT"]),
                     _component("b", "1", licenses=["AGPL-3.0"]))
        report = diff_sboms(base, head)
        self.assertIn("AGPL-3.0", report.new_licenses)

    def test_new_vulnerable(self):
        base = _sbom(_component("a", "1", purl="pkg:npm/a@1"),
                     vulnerabilities=[])
        head = _sbom(_component("a", "1", purl="pkg:npm/a@1"),
                     vulnerabilities=[
                         {"affects": [{"ref": "pkg:npm/a@1"}]}])
        report = diff_sboms(base, head)
        self.assertIn("pkg:npm/a@1", report.new_vulnerable)

    def test_no_changes(self):
        s = _sbom(_component("a", "1"))
        self.assertFalse(diff_sboms(s, s).has_changes)

    def test_bad_input(self):
        with self.assertRaises(SbomDiffError):
            diff_sboms("nope", {})
        with self.assertRaises(SbomDiffError):
            diff_sboms({"components": "x"}, {})

    def test_skips_bad_component_shape(self):
        base = _sbom()
        head = {"components": [
            "string-not-dict",
            {"version": "1"},  # missing name
            _component("ok", "1"),
        ]}
        report = diff_sboms(base, head)
        self.assertEqual([c.name for c in report.added], ["ok"])


class TestAsserts(unittest.TestCase):

    def test_no_new_vuln_pass(self):
        assert_no_new_vulnerable(SbomReport())

    def test_no_new_vuln_fail(self):
        with self.assertRaises(SbomDiffError):
            assert_no_new_vulnerable(SbomReport(new_vulnerable=["x"]))

    def test_disallowed_pass(self):
        assert_no_disallowed_licenses(SbomReport(new_licenses=["MIT"]),
                                      disallowed=["AGPL-3.0"])

    def test_disallowed_fail(self):
        with self.assertRaises(SbomDiffError):
            assert_no_disallowed_licenses(
                SbomReport(new_licenses=["AGPL-3.0"]),
                disallowed=["agpl-3.0"],
            )

    def test_empty_disallowed_rejected(self):
        with self.assertRaises(SbomDiffError):
            assert_no_disallowed_licenses(SbomReport(), disallowed=[])


class TestMarkdown(unittest.TestCase):

    def test_empty(self):
        md = report_markdown(SbomReport())
        self.assertIn("No changes", md)

    def test_renders_all(self):
        report = SbomReport(
            added=[__import__("je_web_runner.utils.sbom_diff.diff",
                              fromlist=["Component"]).Component("a", "1")],
            removed=[__import__("je_web_runner.utils.sbom_diff.diff",
                                fromlist=["Component"]).Component("b", "1")],
            upgraded=[VersionChange("u", "1", "2")],
            downgraded=[VersionChange("d", "2", "1")],
            new_licenses=["MIT"],
            new_vulnerable=["pkg:npm/x@1"],
        )
        md = report_markdown(report)
        self.assertIn("Added", md)
        self.assertIn("Removed", md)
        self.assertIn("Upgraded", md)
        self.assertIn("Downgraded", md)
        self.assertIn("New licenses", md)
        self.assertIn("New vulnerable", md)

    def test_rejects_non_report(self):
        with self.assertRaises(SbomDiffError):
            report_markdown("nope")


if __name__ == "__main__":
    unittest.main()
