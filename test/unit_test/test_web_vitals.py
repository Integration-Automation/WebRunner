"""``WR_assert_web_vitals``: rating, budgets, page and Lighthouse sources, reports."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.web_vitals import vitals
from je_web_runner.utils.web_vitals.vitals import WebVitalsError, assert_web_vitals, evaluate, rate
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

_RAW = {"fcp": 900.0, "lcp": 2100.0, "cls": 0.02, "lcp_element": "img#hero", "lcp_url": "https://x.test/hero.png",
        "cls_sources": [{"node": "div.banner", "value": 0.02}]}
_INP_LOG = [{"name": "pointerdown", "interactionId": 7, "duration_ms": 180.0, "targetTag": None},
            {"name": "click", "interactionId": 7, "duration_ms": 180.0, "targetTag": "BUTTON"},
            {"name": "pointermove", "interactionId": 0, "duration_ms": 400.0}]


def _measurement(**metrics):
    return {"source": "selenium", "url": "https://x.test/", "diagnostics": {},
            "metrics": {"lcp": 2100.0, "cls": 0.02, "inp": 180.0, "fcp": 900.0, **metrics}}


class TestRating(unittest.TestCase):

    def test_google_thresholds(self):
        self.assertEqual(rate("lcp", 2500), "good")
        self.assertEqual(rate("lcp", 2501), "needs-improvement")
        self.assertEqual(rate("lcp", 4001), "poor")
        self.assertEqual(rate("cls", 0.1), "good")
        self.assertEqual(rate("inp", 501), "poor")

    def test_budgets_default_to_good_and_can_be_overridden(self):
        result = evaluate(_measurement(lcp=3000.0))
        self.assertFalse(result["passed"])
        self.assertEqual({row["metric"]: row["status"] for row in result["metrics"]}["lcp"], "fail")
        self.assertTrue(evaluate(_measurement(lcp=3000.0), {"lcp": 3500})["passed"])
        with self.assertRaises(WebVitalsError):
            evaluate(_measurement(), {"ttfb": 100})

    def test_an_unmeasured_metric_is_reported_not_failed(self):
        result = evaluate(_measurement(inp=None))
        self.assertTrue(result["passed"])
        inp = next(row for row in result["metrics"] if row["metric"] == "inp")
        self.assertEqual((inp["status"], inp["rating"]), ("not measured", None))


class TestPageSource(unittest.TestCase):

    def setUp(self):
        self.driver = MagicMock()
        self.driver.current_url = "https://x.test/"
        self.driver.execute_script.side_effect = lambda script: _INP_LOG if "__wr_inp_log__ ||" in script else None
        previous = webdriver_wrapper_instance.current_webdriver
        webdriver_wrapper_instance.current_webdriver = self.driver
        self.addCleanup(setattr, webdriver_wrapper_instance, "current_webdriver", previous)
        patcher = patch.object(vitals, "selenium_collect_metrics", return_value=_RAW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_measures_lcp_cls_fcp_and_inp_with_diagnostics(self):
        result = assert_web_vitals()
        values = {row["metric"]: row["value"] for row in result["metrics"]}
        self.assertEqual(values, {"lcp": 2100.0, "cls": 0.02, "inp": 180.0, "fcp": 900.0})
        self.assertEqual(result["diagnostics"]["lcp_element"], "img#hero")
        self.assertEqual(result["diagnostics"]["slowest_interaction"],
                         {"events": ["click", "pointerdown"], "target": "BUTTON", "duration_ms": 180.0})
        installed = self.driver.execute_script.call_args_list[0].args[0]
        self.assertIn("__wr_inp_installed__", installed)

    def test_a_breach_names_the_metric_rating_and_diagnostics(self):
        with self.assertRaises(WebVitalsError) as caught:
            assert_web_vitals(budgets={"lcp": 1000, "inp": 100})
        message = str(caught.exception)
        self.assertIn("LCP 2100 > 1000 (good)", message)
        self.assertIn("INP 180 > 100 (good)", message)
        self.assertIn("img#hero", message)

    def test_reports_are_written_even_when_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_path, html_path = Path(tmp) / "v.json", Path(tmp) / "out" / "v.html"
            with self.assertRaises(WebVitalsError):
                assert_web_vitals(budgets={"cls": 0.01}, json_path=str(json_path), html_path=str(html_path))
            saved = json.loads(json_path.read_text(encoding="utf-8"))
            page = html_path.read_text(encoding="utf-8")
        self.assertFalse(saved["passed"])
        self.assertIn("<h1>Web Vitals: failed</h1>", page)
        self.assertIn("class='fail'", page)

    def test_html_escapes_page_supplied_text(self):
        result = evaluate(_measurement())
        result["diagnostics"] = {"lcp_element": "<img onerror=alert(1)>"}
        self.assertNotIn("<img onerror", vitals._html(result))


class TestOtherSources(unittest.TestCase):

    def test_no_backend_running(self):
        previous = webdriver_wrapper_instance.current_webdriver
        try:
            webdriver_wrapper_instance.current_webdriver = None
            with patch.object(vitals, "playwright_wrapper_instance") as playwright:
                type(playwright).page = PropertyMock(side_effect=vitals.PlaywrightBackendError("no page"))
                with self.assertRaisesRegex(WebVitalsError, "no Selenium driver or Playwright page"):
                    vitals.measure_page()
        finally:
            webdriver_wrapper_instance.current_webdriver = previous

    def test_playwright_page_runs_the_same_scripts_as_functions(self):
        page = MagicMock(url="https://pw.test/")
        page.evaluate.side_effect = lambda expression: _INP_LOG if "__wr_inp_log__ ||" in expression else None
        run = vitals._playwright_script_runner(page)
        run("(function() { window.x = 1; })();")
        self.assertEqual(page.evaluate.call_args.args[0], "() => { return (function() { window.x = 1; })() }")
        self.assertEqual(run("return window.__wr_inp_log__ || [];"), _INP_LOG)

    def test_lighthouse_reads_its_audits(self):
        report = {"audits": {
            "largest-contentful-paint": {"numericValue": 3200.5},
            "cumulative-layout-shift": {"numericValue": 0.3},
            "first-contentful-paint": {"numericValue": 1200},
            "total-blocking-time": {"numericValue": 150},
            "largest-contentful-paint-element": {
                "details": {"items": [{"items": [{"node": {"selector": "main > h1"}}]}]}},
        }}
        with patch.object(vitals, "run_lighthouse", return_value={"raw": report}) as run:
            with self.assertRaises(WebVitalsError) as caught:
                assert_web_vitals(source="lighthouse", url="https://x.test/")
        run.assert_called_once_with("https://x.test/", lighthouse_path="lighthouse")
        self.assertIn("CLS 0.3 > 0.1 (poor)", str(caught.exception))
        self.assertIn("main > h1", str(caught.exception))

    def test_source_validation(self):
        with self.assertRaises(WebVitalsError):
            assert_web_vitals(source="lighthouse")
        with self.assertRaises(WebVitalsError):
            assert_web_vitals(source="crux")

    def test_registered(self):
        self.assertIn("WR_assert_web_vitals", executor.event_dict)


if __name__ == "__main__":
    unittest.main()
