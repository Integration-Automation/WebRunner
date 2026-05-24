"""Unit tests for je_web_runner.utils.hydration_check."""
import unittest

from je_web_runner.utils.hydration_check.check import (
    HydrationCheckError,
    HydrationFinding,
    HydrationReport,
    assert_no_mismatch,
    audit,
    diff_dom,
    scan_console,
)


class TestScanConsole(unittest.TestCase):

    def test_react_hydration_failed(self):
        findings = scan_console(["Hydration failed because the server rendered HTML didn't match the client."])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, "console")

    def test_did_not_match(self):
        findings = scan_console(["Text content did not match. Server: \"a\" Client: \"b\""])
        self.assertEqual(len(findings), 1)

    def test_vue_hydration_mismatch(self):
        findings = scan_console(["Vue warn: Hydration mismatch in <div>"])
        self.assertEqual(len(findings), 1)

    def test_unrelated_message(self):
        self.assertEqual(scan_console(["TypeError: foo"]), [])

    def test_ignores_non_strings(self):
        self.assertEqual(scan_console([None, 42]), [])  # type: ignore[list-item]


class TestDiffDom(unittest.TestCase):

    def test_identical_passes(self):
        html = "<div>hello</div>"
        self.assertEqual(diff_dom(html, html), [])

    def test_normalises_whitespace(self):
        self.assertEqual(
            diff_dom("<div>hello</div>", "<div>\n  hello\n</div>"),
            [],
        )

    def test_strips_react_attrs(self):
        self.assertEqual(
            diff_dom('<div data-reactroot="">hi</div>', "<div>hi</div>"),
            [],
        )

    def test_strips_svelte_hash(self):
        self.assertEqual(
            diff_dom('<div data-svelte-h="hash">hi</div>', "<div>hi</div>"),
            [],
        )

    def test_strips_vue_scoped(self):
        self.assertEqual(
            diff_dom('<div data-v-abcdef>hi</div>', "<div>hi</div>"),
            [],
        )

    def test_strips_react_text_markers(self):
        self.assertEqual(
            diff_dom("<div><!--$-->Hello<!--/$--></div>", "<div>Hello</div>"),
            [],
        )

    def test_strips_html_comments(self):
        self.assertEqual(
            diff_dom("<div><!-- comment -->hi</div>", "<div>hi</div>"),
            [],
        )

    def test_ignores_script_blocks(self):
        self.assertEqual(
            diff_dom('<div>x</div><script>1+1</script>', '<div>x</div>'),
            [],
        )

    def test_real_divergence_flagged(self):
        findings = diff_dom("<div>server text</div>", "<div>client text</div>")
        self.assertEqual(len(findings), 1)
        self.assertIn("diverged", findings[0].detail)

    def test_rejects_non_string(self):
        with self.assertRaises(HydrationCheckError):
            diff_dom(123, "<div>x</div>")  # type: ignore[arg-type]


class TestAudit(unittest.TestCase):

    def test_clean(self):
        report = audit(
            server_html="<div>x</div>", client_html="<div>x</div>",
            console_messages=["Some unrelated log"],
        )
        self.assertTrue(report.passed())

    def test_dom_only(self):
        report = audit(server_html="<div>a</div>", client_html="<div>b</div>")
        self.assertFalse(report.passed())
        self.assertEqual(report.by_kind(), {"dom_diff": 1})

    def test_console_only(self):
        report = audit(console_messages=["Hydration failed"])
        self.assertFalse(report.passed())
        self.assertEqual(report.by_kind(), {"console": 1})

    def test_both(self):
        report = audit(
            server_html="<div>a</div>", client_html="<div>b</div>",
            console_messages=["Hydration failed"],
        )
        self.assertEqual(sum(report.by_kind().values()), 2)

    def test_empty_audit(self):
        self.assertTrue(audit().passed())


class TestAssert(unittest.TestCase):

    def test_pass(self):
        assert_no_mismatch(HydrationReport())

    def test_fail(self):
        with self.assertRaises(HydrationCheckError):
            assert_no_mismatch(HydrationReport(findings=[
                HydrationFinding(kind="dom_diff", detail="x"),
            ]))

    def test_rejects_non_report(self):
        with self.assertRaises(HydrationCheckError):
            assert_no_mismatch("nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
