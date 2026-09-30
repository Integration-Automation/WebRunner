"""
The interactive HTML report from a real run: headless Chrome with BiDi, the test record on,
failure screenshots on and a HAR recorded, one step failing on purpose. Skips when Chrome
cannot start with BiDi.
"""
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

_PAGE = b"<html><head><title>Report page</title></head><body><h1>hi</h1><script>fetch('/api')</script></body></html>"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — http.server naming
        body = _PAGE if self.path == "/" else b"{}"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


class TestInteractiveReportFromARealRun(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/"  # NOSONAR S5332 — local test server
        try:
            from selenium import webdriver
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.enable_bidi = True
            webdriver_wrapper_instance.current_webdriver = webdriver.Chrome(options=options)
        except Exception as error:  # no Chrome or chromedriver here
            cls.server.shutdown()
            raise unittest.SkipTest(f"Chrome with BiDi is not available: {error!r}")

    @classmethod
    def tearDownClass(cls):
        webdriver_wrapper_instance.current_webdriver.quit()
        webdriver_wrapper_instance.current_webdriver = None
        cls.server.shutdown()

    def setUp(self):
        self.previous_record = (test_record_instance.test_record_list, test_record_instance.init_record)
        test_record_instance.test_record_list = []
        test_record_instance.set_record_enable(True)
        self.addCleanup(self._restore)

    def _restore(self):
        test_record_instance.test_record_list, test_record_instance.init_record = self.previous_record
        executor.set_failure_screenshot_dir(None)

    def test_screenshot_and_waterfall_from_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            shots, har, report = Path(tmp) / "shots", Path(tmp) / "run.har", Path(tmp) / "report"
            executor.set_failure_screenshot_dir(str(shots))
            _record, failed = executor.collect_action_results([
                ["WR_start_har_recording"],
                ["WR_to_url", {"url": self.url}],
                ["WR_wait_for_title", {"pattern": "Report page"}],
                ["WR_wait_for_title", {"pattern": "Another page", "timeout": 0.5}],
                ["WR_stop_har_recording", {"har_path": str(har)}],
                ["WR_generate_interactive_html_report", {"html_name": str(report), "screenshot_dir": str(shots),
                                                         "har_path": str(har)}],
            ])
            page = (Path(tmp) / "report.html").read_text(encoding="utf-8")
        self.assertEqual(len(failed), 1)
        self.assertIn("data:image/png;base64,", page)
        self.assertGreater(page.index("_WR_wait_for_title.png"), page.index("Another page"))
        self.assertIn("Network waterfall", page)
        self.assertIn(self.url + "api", page)
        self.assertIn("1 failed", page)


if __name__ == "__main__":
    unittest.main()
