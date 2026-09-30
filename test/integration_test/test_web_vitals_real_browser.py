"""
``WR_assert_web_vitals`` on a real headless Chrome, through Selenium and through Playwright.

The page shifts its layout once and has a button whose click handler blocks for 250 ms,
so CLS, INP and their diagnostics have something to report. The click waits for the shift:
a shift within 500 ms of input does not count towards CLS, and LCP stops at the first
input. Each backend skips when it cannot start.
"""
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from selenium.webdriver.support.wait import WebDriverWait

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

_PAGE = b"""<html><body style='margin:0;font:16px sans-serif'>
<h1 id='hero' style='font-size:64px;margin:0'>Web vitals</h1>
<div id='spacer'></div>
<p id='text'>Some text that moves when the banner appears.</p>
<button id='slow' onclick='const end = performance.now() + 250; while (performance.now() < end) {}'>slow</button>
<script>setTimeout(() => {
  const banner = document.getElementById('spacer');
  banner.className = 'banner';
  banner.style.height = '200px';
}, 150);</script>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — http.server naming
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(_PAGE)))
        self.end_headers()
        self.wfile.write(_PAGE)

    def log_message(self, *_args):
        return


def _run(action):
    record, failed = executor.collect_action_results([action])
    return next(iter(record.values())), bool(failed)


class _VitalsCases:
    """Shared cases; each subclass starts a backend and knows how to click."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/"  # NOSONAR S5332 — local test server
        try:
            cls._start()
        except Exception as error:  # the backend or its browser is missing here
            cls.server.shutdown()
            raise unittest.SkipTest(f"{cls.__name__} backend is not available: {error!r}")

    @classmethod
    def tearDownClass(cls):
        cls._stop()
        cls.server.shutdown()

    def test_measures_all_four_with_diagnostics(self):
        self._open_and_click()
        result, failed = _run(["WR_assert_web_vitals", {"budgets": {"lcp": 60000, "cls": 5, "inp": 60000,
                                                                     "fcp": 60000}, "observe_ms": 500}])
        self.assertFalse(failed, result)
        values = {row["metric"]: row["value"] for row in result["metrics"]}
        self.assertGreater(values["lcp"], 0)
        self.assertGreater(values["fcp"], 0)
        self.assertGreater(values["cls"], 0)
        self.assertGreaterEqual(values["inp"], 200)
        self.assertEqual(result["diagnostics"]["slowest_interaction"]["target"], "BUTTON")
        self.assertTrue(result["diagnostics"]["lcp_element"])
        self.assertTrue(result["diagnostics"]["cls_sources"])

    def test_the_default_budget_fails_the_slow_click(self):
        self._open_and_click()
        message, failed = _run(["WR_assert_web_vitals", {"observe_ms": 500}])
        self.assertTrue(failed)
        self.assertIn("INP", message)


class TestWebVitalsSelenium(_VitalsCases, unittest.TestCase):

    @classmethod
    def _start(cls):
        from selenium import webdriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        webdriver_wrapper_instance.current_webdriver = webdriver.Chrome(options=options)

    @classmethod
    def _stop(cls):
        webdriver_wrapper_instance.current_webdriver.quit()
        webdriver_wrapper_instance.current_webdriver = None

    def _open_and_click(self):
        driver = webdriver_wrapper_instance.current_webdriver
        driver.get(self.url)
        WebDriverWait(driver, 10).until(lambda d: d.find_elements("css selector", ".banner"))
        time.sleep(0.3)  # let the shift and the LCP entry be reported before the input
        driver.find_element("id", "slow").click()


class TestWebVitalsPlaywright(_VitalsCases, unittest.TestCase):

    @classmethod
    def _start(cls):
        from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
        playwright_wrapper_instance.launch(browser="chromium", headless=True)
        cls.playwright = playwright_wrapper_instance

    @classmethod
    def _stop(cls):
        cls.playwright.quit()

    def _open_and_click(self):
        self.playwright.page.goto(self.url)
        self.playwright.page.wait_for_selector(".banner")
        time.sleep(0.3)  # let the shift and the LCP entry be reported before the input
        self.playwright.page.click("#slow")


if __name__ == "__main__":
    unittest.main()
