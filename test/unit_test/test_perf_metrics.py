import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.perf_metrics.page_metrics import (
    PerfMetricsError,
    assert_metrics_within,
    playwright_collect_metrics,
    selenium_collect_metrics,
)


class TestSeleniumPerfMetrics(unittest.TestCase):

    def test_no_driver_raises(self):
        with patch("je_web_runner.utils.perf_metrics.page_metrics.webdriver_wrapper_instance") as wrapper:
            wrapper.current_webdriver = None
            with self.assertRaises(PerfMetricsError):
                selenium_collect_metrics()

    def test_returns_metrics_dict(self):
        with patch("je_web_runner.utils.perf_metrics.page_metrics.webdriver_wrapper_instance") as wrapper:
            driver = MagicMock()
            wrapper.current_webdriver = driver
            driver.execute_async_script.return_value = {"fcp": 800, "lcp": 1500, "cls": 0.05}
            metrics = selenium_collect_metrics(observe_ms=500)
            self.assertEqual(metrics["fcp"], 800)
            script = driver.execute_async_script.call_args[0][0]
            self.assertIn("PerformanceObserver", script)


class TestPlaywrightPerfMetrics(unittest.TestCase):

    def test_returns_metrics_dict(self):
        with patch("je_web_runner.utils.perf_metrics.page_metrics.playwright_wrapper_instance") as wrapper:
            page = MagicMock()
            wrapper.page = page
            page.evaluate.return_value = {"fcp": 700}
            self.assertEqual(playwright_collect_metrics(800)["fcp"], 700)
            page.evaluate.assert_called_once()
            self.assertEqual(page.evaluate.call_args[0][1], 800)


class TestAssertWithin(unittest.TestCase):

    def test_passes_when_within(self):
        assert_metrics_within({"fcp": 100, "lcp": 200, "cls": 0.0}, {"fcp": 2000, "lcp": 2500, "cls": 0.1})

    def test_raises_when_metric_over(self):
        with self.assertRaises(PerfMetricsError):
            assert_metrics_within({"fcp": 3000}, {"fcp": 2000})

    def test_skips_unknown_metrics(self):
        # If a metric isn't present, no breach should be reported.
        assert_metrics_within({}, {"fcp": 2000})


if __name__ == "__main__":
    unittest.main()
