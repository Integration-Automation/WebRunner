"""Unit tests for je_web_runner.utils.third_party_budget."""
import json
import unittest

from je_web_runner.utils.third_party_budget.budget import (
    ThirdPartyBudget,
    ThirdPartyBudgetError,
    ThirdPartyReport,
    ThirdPartyRequest,
    assert_within_budget,
    classify_har,
    evaluate,
)


def _entry(url, transfer=0, resource_type="script", timings=None):
    return {
        "_resourceType": resource_type,
        "request": {"url": url},
        "response": {"_transferSize": transfer, "content": {"size": transfer}},
        "timings": timings or {"wait": 50, "receive": 10},
    }


def _har(*entries):
    return {"log": {"entries": list(entries)}}


class TestClassify(unittest.TestCase):

    def test_first_party_skipped(self):
        reqs = classify_har(
            _har(_entry("https://app.com/static/a.js")),
            first_party_hostname="app.com",
        )
        self.assertEqual(reqs, [])

    def test_first_party_subdomain_skipped(self):
        reqs = classify_har(
            _har(_entry("https://cdn.app.com/a.js")),
            first_party_hostname="app.com",
        )
        self.assertEqual(reqs, [])

    def test_known_vendor_tagged(self):
        reqs = classify_har(
            _har(_entry("https://www.google-analytics.com/ga.js", transfer=10_000)),
            first_party_hostname="app.com",
        )
        self.assertEqual(reqs[0].vendor, "google_analytics")
        self.assertEqual(reqs[0].bytes_transferred, 10_000)

    def test_unknown_third_party_tagged(self):
        reqs = classify_har(
            _har(_entry("https://random-ad-network.com/track.js")),
            first_party_hostname="app.com",
        )
        self.assertEqual(reqs[0].vendor, "unknown_third_party")

    def test_extra_vendor(self):
        reqs = classify_har(
            _har(_entry("https://myco-analytics.com/x.js")),
            first_party_hostname="app.com",
            extra_vendors={"myco": ("myco-analytics.com",)},
        )
        self.assertEqual(reqs[0].vendor, "myco")

    def test_subdomain_vendor_matches(self):
        reqs = classify_har(
            _har(_entry("https://collect.www.google-analytics.com/g/x")),
            first_party_hostname="app.com",
        )
        self.assertEqual(reqs[0].vendor, "google_analytics")

    def test_duration_summed_from_timings(self):
        reqs = classify_har(
            _har(_entry("https://cdn.segment.com/a.js",
                        timings={"wait": 100, "receive": 20, "blocked": 5})),
            first_party_hostname="app.com",
        )
        self.assertEqual(reqs[0].duration_ms, 125)

    def test_blocking_flag(self):
        reqs = classify_har(
            _har(_entry("https://cdn.segment.com/a.js", resource_type="script"),
                 _entry("https://cdn.segment.com/img.png", resource_type="image")),
            first_party_hostname="app.com",
        )
        self.assertTrue(reqs[0].blocking)
        self.assertFalse(reqs[1].blocking)

    def test_skips_no_url(self):
        reqs = classify_har(
            _har({"request": {}, "response": {}}),
            first_party_hostname="app.com",
        )
        self.assertEqual(reqs, [])

    def test_str_har(self):
        reqs = classify_har(
            json.dumps(_har(_entry("https://cdn.segment.com/a.js"))),
            first_party_hostname="app.com",
        )
        self.assertEqual(len(reqs), 1)

    def test_bad_har(self):
        with self.assertRaises(ThirdPartyBudgetError):
            classify_har("nope", first_party_hostname="app.com")

    def test_bad_first_party(self):
        with self.assertRaises(ThirdPartyBudgetError):
            classify_har(_har(), first_party_hostname="")


class TestBudget(unittest.TestCase):

    def test_negative_rejected(self):
        with self.assertRaises(ThirdPartyBudgetError):
            ThirdPartyBudget(max_requests=-1)
        with self.assertRaises(ThirdPartyBudgetError):
            ThirdPartyBudget(max_bytes=-1)


class TestEvaluate(unittest.TestCase):

    def _reqs(self, *configs):
        out = []
        for url, size, blocking, vendor in configs:
            out.append(ThirdPartyRequest(
                url=url, vendor=vendor, hostname="x",
                bytes_transferred=size, duration_ms=size / 10,
                blocking=blocking,
            ))
        return out

    def test_passes(self):
        report = evaluate(
            self._reqs(
                ("https://x/a", 1000, True, "google_analytics"),
                ("https://y/b", 2000, False, "stripe"),
            ),
            ThirdPartyBudget(max_requests=10, max_bytes=10_000),
        )
        self.assertTrue(report.passed())
        self.assertEqual(report.total_bytes, 3000)

    def test_breach_requests(self):
        report = evaluate(
            self._reqs(*[("https://x/a", 1, True, "ga")] * 5),
            ThirdPartyBudget(max_requests=2),
        )
        self.assertFalse(report.passed())

    def test_breach_bytes(self):
        report = evaluate(
            self._reqs(("https://x/a", 10_000, True, "ga")),
            ThirdPartyBudget(max_bytes=1000),
        )
        self.assertFalse(report.passed())

    def test_breach_blocking_ms(self):
        report = evaluate(
            self._reqs(("https://x/a", 10_000, True, "ga")),
            ThirdPartyBudget(max_blocking_ms=100),
        )
        # duration_ms = 10_000 / 10 = 1000 > 100
        self.assertFalse(report.passed())

    def test_breach_vendors(self):
        report = evaluate(
            self._reqs(
                ("https://a", 1, True, "ga"),
                ("https://b", 1, True, "stripe"),
                ("https://c", 1, True, "hotjar"),
            ),
            ThirdPartyBudget(max_vendors=2),
        )
        self.assertFalse(report.passed())

    def test_by_vendor_aggregation(self):
        report = evaluate(
            self._reqs(
                ("https://a", 100, True, "ga"),
                ("https://b", 200, False, "ga"),
            ),
            ThirdPartyBudget(),
        )
        self.assertEqual(report.by_vendor["ga"]["requests"], 2)
        self.assertEqual(report.by_vendor["ga"]["bytes"], 300)

    def test_rejects_non_request(self):
        with self.assertRaises(ThirdPartyBudgetError):
            evaluate(["not a request"], ThirdPartyBudget())  # type: ignore[list-item]

    def test_rejects_non_budget(self):
        with self.assertRaises(ThirdPartyBudgetError):
            evaluate([], "not a budget")  # type: ignore[arg-type]


class TestAssert(unittest.TestCase):

    def test_pass(self):
        assert_within_budget(ThirdPartyReport())

    def test_fail(self):
        with self.assertRaises(ThirdPartyBudgetError):
            assert_within_budget(ThirdPartyReport(breaches=["x"]))

    def test_rejects_non_report(self):
        with self.assertRaises(ThirdPartyBudgetError):
            assert_within_budget("nope")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
