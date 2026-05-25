"""Unit tests for je_web_runner.utils.bundle_diff_pr."""
import unittest

from je_web_runner.utils.bundle_diff_pr.diff import (
    AssetDelta,
    BundleDiff,
    BundleDiffPrError,
    assert_under_max_growth,
    diff_hars,
    report_markdown,
)


def _entry(url, transfer, rt="script"):
    return {
        "_resourceType": rt,
        "request": {"url": url},
        "response": {"_transferSize": transfer,
                     "content": {"size": transfer}},
    }


def _har(*entries):
    return {"log": {"entries": list(entries)}}


class TestDiff(unittest.TestCase):

    def test_added_removed_grew_shrunk(self):
        base = _har(
            _entry("/a.js", 1000),
            _entry("/b.js", 500),
            _entry("/c.js", 800),
        )
        head = _har(
            _entry("/a.js", 1500),  # grew
            _entry("/b.js", 500),   # unchanged
            _entry("/d.js", 200),   # added
            # /c.js removed
        )
        diff = diff_hars(base, head)
        urls = {d.url for d in diff.grew}
        self.assertIn("/a.js", urls)
        self.assertEqual(diff.unchanged, 1)
        added_urls = {d.url for d in diff.added}
        self.assertIn("/d.js", added_urls)
        removed_urls = {d.url for d in diff.removed}
        self.assertIn("/c.js", removed_urls)
        # total delta = +500 (a) + 200 (d added) - 800 (c removed) = -100
        self.assertEqual(diff.total_delta_bytes, -100)

    def test_shrunk(self):
        base = _har(_entry("/x.js", 2000))
        head = _har(_entry("/x.js", 1500))
        diff = diff_hars(base, head)
        self.assertEqual(len(diff.shrunk), 1)
        self.assertEqual(diff.shrunk[0].delta, -500)

    def test_percent_handles_zero_base(self):
        delta = AssetDelta(url="x", kind=__import__(
            "je_web_runner.utils.bundle_budget.budget", fromlist=["AssetKind"]
        ).AssetKind.SCRIPT, base_bytes=0, head_bytes=100)
        self.assertEqual(delta.percent, 100.0)

    def test_regressions_filter(self):
        diff = BundleDiff(added=[
            AssetDelta(url="big", kind=__import__(
                "je_web_runner.utils.bundle_budget.budget", fromlist=["AssetKind"]
            ).AssetKind.SCRIPT, base_bytes=0, head_bytes=5000),
            AssetDelta(url="small", kind=__import__(
                "je_web_runner.utils.bundle_budget.budget", fromlist=["AssetKind"]
            ).AssetKind.SCRIPT, base_bytes=0, head_bytes=500),
        ])
        self.assertEqual(len(diff.regressions(min_bytes=1024)), 1)

    def test_regressions_bad_arg(self):
        with self.assertRaises(BundleDiffPrError):
            BundleDiff().regressions(min_bytes=-1)


class TestAssertGrowth(unittest.TestCase):

    def test_pass(self):
        diff = BundleDiff(total_delta_bytes=1000)
        assert_under_max_growth(diff, max_growth_bytes=2000)

    def test_fail(self):
        with self.assertRaises(BundleDiffPrError):
            assert_under_max_growth(
                BundleDiff(total_delta_bytes=5000), max_growth_bytes=1000,
            )

    def test_bad_threshold(self):
        with self.assertRaises(BundleDiffPrError):
            assert_under_max_growth(BundleDiff(), max_growth_bytes=-1)


class TestMarkdown(unittest.TestCase):

    def test_renders(self):
        base = _har(_entry("/a.js", 1000))
        head = _har(_entry("/a.js", 5000))
        md = report_markdown(diff_hars(base, head))
        self.assertIn("Bundle delta", md)
        self.assertIn("Largest regressions", md)
        self.assertIn("/a.js", md)

    def test_rejects_non_diff(self):
        with self.assertRaises(BundleDiffPrError):
            report_markdown("nope")

    def test_bad_top_n(self):
        with self.assertRaises(BundleDiffPrError):
            report_markdown(BundleDiff(), top_n=-1)


if __name__ == "__main__":
    unittest.main()
