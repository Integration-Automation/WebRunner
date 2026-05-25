"""Unit tests for je_web_runner.utils.inbox_render_outlook."""
import unittest

from je_web_runner.utils.inbox_render_outlook.render import (
    InboxRenderOutlookError,
    RenderFinding,
    Severity,
    assert_no_errors,
    audit_all,
    audit_apple_mail,
    audit_gmail,
    audit_outlook,
)


CLEAN_TABLE = (
    "<html><body><table><tr><td>Hi</td></tr></table>"
    "<style>@media (prefers-color-scheme: dark){body{background:#000}}</style>"
    "</body></html>"
)


class TestOutlook(unittest.TestCase):

    def test_flex_warn(self):
        findings = audit_outlook("<html><body style='display:flex'></body></html>")
        rules = {f.rule for f in findings}
        self.assertIn("outlook-incompatible-css", rules)

    def test_svg_error(self):
        findings = audit_outlook("<svg width='10' height='10'></svg>")
        self.assertIn("outlook-no-svg", {f.rule for f in findings})

    def test_no_table_warn(self):
        findings = audit_outlook("<div>x</div>")
        self.assertIn("outlook-needs-table-layout", {f.rule for f in findings})

    def test_clean(self):
        findings = audit_outlook("<table><tr><td>x</td></tr></table>")
        rules = {f.rule for f in findings}
        self.assertNotIn("outlook-incompatible-css", rules)

    def test_bad_input(self):
        with self.assertRaises(InboxRenderOutlookError):
            audit_outlook(123)  # NOSONAR python:S5655 - deliberate bad input


class TestGmail(unittest.TestCase):

    def test_media_query_warning(self):
        findings = audit_gmail("<style>@media (max-width:600px){}</style>")
        rules = {f.rule for f in findings}
        self.assertIn("gmail-media-queries-need-inline", rules)

    def test_clipping(self):
        large = "<html>" + "x" * (110 * 1024) + "</html>"
        findings = audit_gmail(large)
        rules = {f.rule for f in findings}
        self.assertIn("gmail-message-clipping", rules)

    def test_clean(self):
        self.assertEqual(audit_gmail("<p>x</p>"), [])


class TestAppleMail(unittest.TestCase):

    def test_no_dark_mode(self):
        findings = audit_apple_mail("<html><body>x</body></html>")
        rules = {f.rule for f in findings}
        self.assertIn("apple-mail-dark-mode", rules)

    def test_has_dark_mode(self):
        findings = audit_apple_mail(CLEAN_TABLE)
        rules = {f.rule for f in findings}
        self.assertNotIn("apple-mail-dark-mode", rules)


class TestAll(unittest.TestCase):

    def test_combines(self):
        findings = audit_all("<svg></svg><div>x</div>")
        # both outlook + gmail + apple emit at least one finding each
        self.assertGreaterEqual(len(findings), 3)


class TestAssertNoErrors(unittest.TestCase):

    def test_pass(self):
        assert_no_errors([RenderFinding(rule="x", severity=Severity.WARN,
                                        message="")])

    def test_fail(self):
        with self.assertRaises(InboxRenderOutlookError):
            assert_no_errors([RenderFinding(rule="x", severity=Severity.ERROR,
                                            message="")])


if __name__ == "__main__":
    unittest.main()
