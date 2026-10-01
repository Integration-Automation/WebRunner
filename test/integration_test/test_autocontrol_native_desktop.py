"""
The native ``WR_ac_*`` commands on a real desktop, with a visible Chrome.

They move the real mouse and type into the real screen, so they run only with
``WEBRUNNER_NATIVE_DESKTOP_TESTS=1`` on a desktop nothing else is driving (not beside a
running Jeffrey_RPA batch), and skip without ``je_auto_control`` or Chrome.
"""
import base64
import importlib.util
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from selenium.webdriver.support.wait import WebDriverWait

from je_web_runner.utils.autocontrol_bridge.screen_mapping import METRICS_SCRIPT, element_center_on_screen
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

_ENABLED = os.environ.get("WEBRUNNER_NATIVE_DESKTOP_TESTS") == "1"
_PAGE = """data:text/html,<html><body style='margin:0'>
<div id='box' style='position:absolute;left:300px;top:200px;width:120px;height:80px;
 background:linear-gradient(90deg,%23c0392b,%2327ae60,%232980b9)'></div>
<button id='b' style='position:absolute;left:600px;top:400px;width:140px;height:40px'
 onclick="document.getElementById('out').textContent=String(event.isTrusted)">native</button>
<input id='f' type='file' style='position:absolute;left:600px;top:500px'>
<div id='out'></div></body></html>"""


class _BasicAuthHandler(BaseHTTPRequestHandler):
    """A page behind HTTP basic auth: 401 with a challenge until the expected credentials arrive."""

    expected = ""

    def do_GET(self):  # noqa: N802 — http.server naming
        if self.headers.get("Authorization") != self.expected:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="webrunner"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = b"<html><body><p id='who'>signed in</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


def _run(action):
    record, failed = executor.collect_action_results([action])
    if failed:
        raise AssertionError(next(iter(record.values())))
    return next(iter(record.values()))


@unittest.skipUnless(_ENABLED, "set WEBRUNNER_NATIVE_DESKTOP_TESTS=1 on a desktop nothing else is driving")
@unittest.skipIf(importlib.util.find_spec("je_auto_control") is None, "je_auto_control is not installed")
class TestNativeDesktop(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from selenium import webdriver
        try:
            webdriver_wrapper_instance.current_webdriver = webdriver.Chrome()
        except Exception as error:  # no Chrome or chromedriver here
            raise unittest.SkipTest(f"Chrome is not available: {error!r}")
        webdriver_wrapper_instance.current_webdriver.maximize_window()

    @classmethod
    def tearDownClass(cls):
        webdriver_wrapper_instance.current_webdriver.quit()
        webdriver_wrapper_instance.current_webdriver = None

    def setUp(self):
        self.driver = webdriver_wrapper_instance.current_webdriver
        self.driver.get(_PAGE)

    def test_a_native_click_is_a_trusted_event(self):
        _run(["WR_ac_click_element_native", {"selector": "#b"}])
        self.assertEqual(self.driver.find_element("id", "out").text, "true")

    def test_the_mapped_centre_is_where_the_image_is_found(self):
        box = self.driver.find_element("id", "box")
        with tempfile.TemporaryDirectory() as tmp:
            template = str(Path(tmp) / "box.png")
            box.screenshot(template)
            found = _run(["WR_ac_assert_image_on_screen", {"image_path": template}])
        mapped = element_center_on_screen(self.driver.execute_script(METRICS_SCRIPT, box))
        self.assertLessEqual(abs(found[0] - mapped[0]), 3, (found, mapped))
        self.assertLessEqual(abs(found[1] - mapped[1]), 3, (found, mapped))

    def test_a_file_chosen_in_the_native_dialog(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as chosen:
            chosen.write(b"picked natively")
        self.addCleanup(os.remove, chosen.name)
        _run(["WR_ac_click_element_native", {"selector": "#f"}])
        _run(["WR_ac_fill_native_file_dialog", {"file_path": chosen.name, "wait_seconds": 2}])
        name = self.driver.execute_script("return document.getElementById('f').files[0]?.name || ''")
        self.assertEqual(name, Path(chosen.name).name)

    def test_basic_auth_typed_into_the_browser_dialog(self):
        user, password = "Al1ce", "S3cret,Pa55!"  # capitals and punctuation must arrive exactly
        _BasicAuthHandler.expected = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        server = ThreadingHTTPServer(("127.0.0.1", 0), _BasicAuthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_address[1]}/private"  # NOSONAR S5332 — local test server
        with patch.dict(os.environ, {"WR_DESKTOP_USER": user, "WR_DESKTOP_PASS": password}):
            _run(["WR_ac_basic_auth", {"username_env": "WR_DESKTOP_USER", "password_env": "WR_DESKTOP_PASS",
                                       "url": url, "wait_seconds": 2}])
        WebDriverWait(self.driver, 15).until(lambda driver: driver.find_elements("id", "who"))
        self.assertEqual(self.driver.find_element("id", "who").text, "signed in")


if __name__ == "__main__":
    unittest.main()
