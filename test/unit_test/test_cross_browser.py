import unittest

from je_web_runner.utils.cross_browser import (
    CrossBrowserError,
    diff_runs,
)
from je_web_runner.utils.cross_browser.parity import (
    BrowserRunResult,
    assert_parity,
)


def _result(browser="chromium", title="X", dom="<html></html>",
            console=None, network=None, screenshot=None):
    return BrowserRunResult(
        browser=browser,
        title=title,
        dom_text=dom,
        console=console or [],
        network=network or [],
        screenshot=screenshot,
    )


class TestDiffRuns(unittest.TestCase):

    def test_identical_runs_match(self):
        runs = [_result(browser="chromium"), _result(browser="firefox")]
        report = diff_runs(runs)
        self.assertTrue(report.matches)

    def test_title_mismatch_major(self):
        runs = [
            _result(browser="chromium", title="A"),
            _result(browser="firefox", title="B"),
        ]
        report = diff_runs(runs, reference_browser="chromium")
        findings = report.findings_by_browser["firefox"]
        self.assertTrue(any(f.field == "title" and f.severity == "major" for f in findings))

    def test_dom_mismatch_major(self):
        runs = [
            _result(browser="chromium", dom="<html>a</html>"),
            _result(browser="firefox", dom="<html>b</html>"),
        ]
        report = diff_runs(runs)
        findings = report.findings_by_browser["firefox"]
        self.assertTrue(any(f.field == "dom_hash" for f in findings))

    def test_console_mismatch_minor(self):
        runs = [
            _result(browser="chromium",
                    console=[{"type": "error", "text": "boom"}]),
            _result(browser="firefox", console=[]),
        ]
        report = diff_runs(runs)
        findings = report.findings_by_browser["firefox"]
        self.assertTrue(any(f.field == "console" and f.severity == "minor" for f in findings))

    def test_5xx_network_diff_is_major(self):
        runs = [
            _result(browser="chromium",
                    network=[{"url": "/x", "status": 200}]),
            _result(browser="firefox",
                    network=[{"url": "/x", "status": 503}]),
        ]
        report = diff_runs(runs)
        findings = report.findings_by_browser["firefox"]
        major = [f for f in findings if f.field == "network_status"]
        self.assertTrue(major and major[0].severity == "major")

    def test_screenshot_diff_minor(self):
        runs = [
            _result(browser="chromium", screenshot=b"a"),
            _result(browser="firefox", screenshot=b"b"),
        ]
        report = diff_runs(runs)
        findings = report.findings_by_browser["firefox"]
        self.assertTrue(any(f.field == "screenshot_hash"
                            and f.severity == "minor" for f in findings))

    def test_duplicate_browser_raises(self):
        with self.assertRaises(CrossBrowserError):
            diff_runs([
                _result(browser="chromium"),
                _result(browser="chromium"),
            ])

    def test_unknown_reference_raises(self):
        with self.assertRaises(CrossBrowserError):
            diff_runs([_result(browser="chromium")], reference_browser="webkit")

    def test_invalid_input_type(self):
        with self.assertRaises(CrossBrowserError):
            diff_runs(["not a result"])  # type: ignore[list-item]

    def test_empty_input(self):
        with self.assertRaises(CrossBrowserError):
            diff_runs([])


class TestAssertParity(unittest.TestCase):

    def test_passes_when_no_major(self):
        runs = [
            _result(browser="chromium", console=[{"type": "log", "text": "a"}]),
            _result(browser="firefox", console=[]),
        ]
        report = diff_runs(runs)
        # console diff is minor → only_major=True passes
        assert_parity(report)

    def test_raises_on_major(self):
        runs = [
            _result(browser="chromium", title="A"),
            _result(browser="firefox", title="B"),
        ]
        report = diff_runs(runs)
        with self.assertRaises(CrossBrowserError):
            assert_parity(report)

    def test_allow_field_skips(self):
        runs = [
            _result(browser="chromium", title="A"),
            _result(browser="firefox", title="B"),
        ]
        report = diff_runs(runs)
        assert_parity(report, allow_fields=["title"])


if __name__ == "__main__":
    unittest.main()
