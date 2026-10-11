"""
Selenium event capture, HAR and response mocks over W3C BiDi, against real headless Chrome
and Firefox.

Pages come from a local HTTP server because ``data:`` URLs make no network events. Each
browser skips when it cannot start with BiDi.
"""
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from je_web_runner.utils.bidi.selenium_events import selenium_bidi_events
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

_PAGE = b"""<html><body><div id='out'></div><script>
console.log('hello');
console.error('boom');
fetch('/api/data').then((r) => r.json()).then((d) => { document.getElementById('out').textContent = d.value; });
setTimeout(() => { const p = document.createElement('p'); p.id = 'added'; document.body.appendChild(p); }, 200);
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 — http.server naming
        body, kind = (_PAGE, "text/html") if self.path == "/" else (b'{"value": "real"}', "application/json")
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def _wait_for(check, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.1)
    return False


class _SeleniumBidiCases:
    """The cases; each browser subclass starts its own driver."""

    browser = ""

    @staticmethod
    def _start_driver():
        raise NotImplementedError

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/"  # NOSONAR S5332 — local test server
        try:
            webdriver_wrapper_instance.current_webdriver = cls._start_driver()
        except Exception as error:  # no such browser or driver here
            cls.server.shutdown()
            raise unittest.SkipTest(f"{cls.browser} with BiDi is not available: {error!r}")

    @classmethod
    def tearDownClass(cls):
        webdriver_wrapper_instance.current_webdriver.quit()
        webdriver_wrapper_instance.current_webdriver = None
        cls.server.shutdown()

    def tearDown(self):
        selenium_bidi_events.stop_event_capture()
        selenium_bidi_events.clear_event_capture()
        selenium_bidi_events.route_clear()

    def _driver(self):
        return webdriver_wrapper_instance.current_webdriver

    def test_capture_console_errors_responses_and_dom_mutations(self):
        executor.collect_action_results([["WR_event_capture_start", {"dom_mutations": True}]])
        self._driver().get(self.url)
        self.assertTrue(_wait_for(lambda: any(m.get("added") for m in selenium_bidi_events.dom_mutations)))
        self.assertTrue(_wait_for(lambda: any(r["url"].endswith("/api/data")
                                              for r in selenium_bidi_events.network_responses())))
        texts = {(m["type"], m["text"]) for m in selenium_bidi_events.console_messages()}
        self.assertIn(("info", "hello"), texts)
        self.assertIn(("error", "boom"), texts)
        _record, failed = executor.collect_action_results([["WR_assert_no_console_errors"]])
        self.assertEqual(len(failed), 1)
        _record, failed = executor.collect_action_results([["WR_assert_no_5xx"]])
        self.assertEqual(failed, [])

    def test_route_mock_answers_matching_requests_only(self):
        executor.collect_action_results([["WR_route_mock_json", {"url_pattern": "*/api/data",
                                                                 "json_data": {"value": "mocked"}}]])
        self._driver().get(self.url)
        out = lambda: self._driver().find_element("id", "out").text  # noqa: E731
        self.assertTrue(_wait_for(lambda: out() == "mocked"), out())
        executor.collect_action_results([["WR_route_clear"]])
        self._driver().get(self.url)
        self.assertTrue(_wait_for(lambda: out() == "real"), out())

    def test_har_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            har = str(Path(tmp) / "run.har")
            executor.collect_action_results([["WR_start_har_recording"]])
            self._driver().get(self.url)
            self.assertTrue(_wait_for(lambda: self._driver().find_element("id", "out").text == "real"))
            time.sleep(0.3)
            executor.collect_action_results([["WR_stop_har_recording", {"har_path": har}]])
            log = json.loads(Path(har).read_text(encoding="utf-8"))["log"]
        entries = {entry["request"]["url"]: entry for entry in log["entries"]}
        self.assertEqual(log["version"], "1.2")
        self.assertEqual(entries[self.url + "api/data"]["response"]["status"], 200)
        self.assertEqual(entries[self.url]["request"]["method"], "GET")


class TestSeleniumBidiChrome(_SeleniumBidiCases, unittest.TestCase):
    browser = "Chrome"

    @staticmethod
    def _start_driver():
        from selenium import webdriver
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.enable_bidi = True
        return webdriver.Chrome(options=options)


class TestSeleniumBidiFirefox(_SeleniumBidiCases, unittest.TestCase):
    browser = "Firefox"

    @staticmethod
    def _start_driver():
        from selenium import webdriver
        options = webdriver.FirefoxOptions()
        options.add_argument("-headless")
        options.enable_bidi = True
        return webdriver.Firefox(options=options)


if __name__ == "__main__":
    unittest.main()
