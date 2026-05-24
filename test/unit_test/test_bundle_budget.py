"""Unit tests for je_web_runner.utils.bundle_budget."""
import json
import unittest

from je_web_runner.utils.bundle_budget.budget import (
    Asset,
    AssetKind,
    Budget,
    BudgetBreach,
    BudgetReport,
    BundleBudgetError,
    DEFAULT_BUDGETS,
    assert_within_budget,
    assets_from_har,
    evaluate_budget,
    report_markdown,
)


def _entry(url, resource_type, transfer=0, content_size=None, mime=""):
    if content_size is None:
        content_size = transfer
    return {
        "_resourceType": resource_type,
        "request": {"url": url},
        "response": {
            "_transferSize": transfer,
            "bodySize": transfer,
            "content": {"size": content_size, "mimeType": mime},
        },
    }


def _har(*entries):
    return {"log": {"entries": list(entries)}}


class TestAssetsFromHar(unittest.TestCase):

    def test_basic_classification(self):
        har = _har(
            _entry("https://x/a.js", "script", transfer=100),
            _entry("https://x/a.css", "stylesheet", transfer=200),
            _entry("https://x/a.png", "image", transfer=300),
        )
        assets = assets_from_har(har)
        kinds = [a.kind for a in assets]
        self.assertEqual(kinds, [AssetKind.SCRIPT, AssetKind.STYLESHEET, AssetKind.IMAGE])

    def test_mime_fallback(self):
        # No resource_type → fall back to mime type
        har = _har({
            "request": {"url": "https://x/a.woff2"},
            "response": {
                "_transferSize": 50,
                "content": {"size": 50, "mimeType": "font/woff2"},
            },
        })
        assets = assets_from_har(har)
        self.assertEqual(assets[0].kind, AssetKind.FONT)

    def test_image_mime_prefix(self):
        har = _har({
            "request": {"url": "https://x/a.bmp"},
            "response": {"content": {"size": 1, "mimeType": "image/bmp"}},
        })
        self.assertEqual(assets_from_har(har)[0].kind, AssetKind.IMAGE)

    def test_unknown_other(self):
        har = _har({
            "request": {"url": "https://x/a.bin"},
            "response": {"content": {"mimeType": "application/octet-stream"}},
        })
        self.assertEqual(assets_from_har(har)[0].kind, AssetKind.OTHER)

    def test_skips_no_url(self):
        har = _har({"request": {}, "response": {}})
        self.assertEqual(assets_from_har(har), [])

    def test_str_har(self):
        assets = assets_from_har(json.dumps(_har(_entry("https://x/a.js", "script"))))
        self.assertEqual(len(assets), 1)

    def test_bad_har(self):
        with self.assertRaises(BundleBudgetError):
            assets_from_har("nope")

    def test_bad_har_type(self):
        with self.assertRaises(BundleBudgetError):
            assets_from_har(123)  # type: ignore[arg-type]

    def test_bad_har_root(self):
        with self.assertRaises(BundleBudgetError):
            assets_from_har("[]")


class TestBudget(unittest.TestCase):

    def test_rejects_zero(self):
        with self.assertRaises(BundleBudgetError):
            Budget(kind=AssetKind.SCRIPT, max_bytes=0)


class TestEvaluate(unittest.TestCase):

    def test_pass(self):
        assets = [
            Asset(url="x", kind=AssetKind.SCRIPT, transfer_bytes=100_000, content_bytes=100_000),
        ]
        report = evaluate_budget(assets)
        self.assertTrue(report.passed())

    def test_breach(self):
        assets = [
            Asset(url="x", kind=AssetKind.SCRIPT,
                  transfer_bytes=500_000, content_bytes=500_000),
        ]
        report = evaluate_budget(assets)
        self.assertFalse(report.passed())
        self.assertEqual(report.breaches[0].kind, AssetKind.SCRIPT)
        self.assertGreater(report.breaches[0].over_bytes, 0)

    def test_uses_larger_of_transfer_content(self):
        assets = [
            Asset(url="x", kind=AssetKind.IMAGE,
                  transfer_bytes=100_000, content_bytes=1_000_000),
        ]
        report = evaluate_budget(assets)
        self.assertEqual(report.totals[AssetKind.IMAGE], 1_000_000)

    def test_biggest_n(self):
        assets = [
            Asset(url=f"u{i}", kind=AssetKind.SCRIPT,
                  transfer_bytes=i, content_bytes=i)
            for i in range(1, 15)
        ]
        report = evaluate_budget(assets, biggest_n=3)
        self.assertEqual(len(report.biggest_assets), 3)
        self.assertEqual(report.biggest_assets[0].url, "u14")

    def test_custom_budget(self):
        assets = [Asset(url="x", kind=AssetKind.SCRIPT,
                        transfer_bytes=200, content_bytes=200)]
        report = evaluate_budget(
            assets, budgets=[Budget(kind=AssetKind.SCRIPT, max_bytes=100)],
        )
        self.assertFalse(report.passed())

    def test_empty_assets(self):
        with self.assertRaises(BundleBudgetError):
            evaluate_budget([])

    def test_bad_biggest_n(self):
        with self.assertRaises(BundleBudgetError):
            evaluate_budget([Asset(url="x", kind=AssetKind.SCRIPT,
                                   transfer_bytes=1, content_bytes=1)],
                            biggest_n=-1)

    def test_bad_budget_entry(self):
        with self.assertRaises(BundleBudgetError):
            evaluate_budget(
                [Asset(url="x", kind=AssetKind.SCRIPT,
                       transfer_bytes=1, content_bytes=1)],
                budgets=["not a budget"],  # type: ignore[list-item]
            )


class TestAssertReport(unittest.TestCase):

    def test_pass(self):
        assert_within_budget(BudgetReport())

    def test_fail(self):
        report = BudgetReport(breaches=[BudgetBreach(
            kind=AssetKind.SCRIPT, actual_bytes=2, max_bytes=1, over_bytes=1,
        )])
        with self.assertRaises(BundleBudgetError):
            assert_within_budget(report)

    def test_rejects_non_report(self):
        with self.assertRaises(BundleBudgetError):
            assert_within_budget("nope")  # type: ignore[arg-type]


class TestMarkdown(unittest.TestCase):

    def test_renders(self):
        report = BudgetReport(
            totals={AssetKind.SCRIPT: 100},
            breaches=[BudgetBreach(AssetKind.SCRIPT, 100, 50, 50)],
            biggest_assets=[Asset(url="x", kind=AssetKind.SCRIPT,
                                  transfer_bytes=100, content_bytes=100)],
        )
        md = report_markdown(report)
        self.assertIn("Bundle budget", md)
        self.assertIn("Breaches", md)
        self.assertIn("script", md)

    def test_rejects_non_report(self):
        with self.assertRaises(BundleBudgetError):
            report_markdown("nope")  # type: ignore[arg-type]


class TestDefaults(unittest.TestCase):

    def test_default_budgets_loaded(self):
        kinds = {b.kind for b in DEFAULT_BUDGETS}
        self.assertIn(AssetKind.SCRIPT, kinds)
        self.assertIn(AssetKind.IMAGE, kinds)


if __name__ == "__main__":
    unittest.main()
