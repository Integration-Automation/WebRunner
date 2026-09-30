"""Selenium BiDi event capture, HAR and response mocks against a fake BiDi connection."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import WebDriverException

from je_web_runner.utils.bidi import selenium_events
from je_web_runner.utils.bidi.selenium_events import (
    BidiEventsError,
    SeleniumBidiEvents,
    to_bidi_url_pattern,
)
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.observability.event_capture import EventCaptureError
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


def _fake_driver():
    driver = MagicMock()
    driver.caps = {"webSocketUrl": "ws://127.0.0.1:9/session"}
    counter = iter(range(1, 100))
    driver.network.conn.execute.side_effect = lambda command: (
        {"intercept": f"i{next(counter)}"} if command[0] == "network.addIntercept" else {})
    return driver


def _sent(driver, method):
    return [call.args[0][1] for call in driver.network.conn.execute.call_args_list if call.args[0][0] == method]


class _BidiCase(unittest.TestCase):

    def setUp(self):
        self.driver = _fake_driver()
        self.previous = webdriver_wrapper_instance.current_webdriver
        webdriver_wrapper_instance.current_webdriver = self.driver
        command = patch.object(selenium_events, "_command", lambda method, params: (method, params))
        command.start()
        self.addCleanup(command.stop)
        self.events = SeleniumBidiEvents()

    def tearDown(self):
        webdriver_wrapper_instance.current_webdriver = self.previous


class TestUrlPatterns(unittest.TestCase):

    def test_exact_url_path_and_parts(self):
        self.assertEqual(to_bidi_url_pattern("https://a.test/api?x=1"),
                         {"type": "string", "pattern": "https://a.test/api?x=1"})
        self.assertEqual(to_bidi_url_pattern("*/api/data"), {"type": "pattern", "pathname": "/api/data"})
        self.assertEqual(to_bidi_url_pattern("**/api/data"), {"type": "pattern", "pathname": "/api/data"})
        self.assertEqual(to_bidi_url_pattern({"hostname": "a.test", "port": 8080}),
                         {"type": "pattern", "hostname": "a.test", "port": "8080"})

    def test_unsupported_patterns_raise(self):
        for pattern in ("", "https://a.test/*.js", "*/api/*", {"path": "/x"}, 5):
            with self.subTest(pattern=pattern), self.assertRaises(BidiEventsError):
                to_bidi_url_pattern(pattern)


class TestDriverChecks(unittest.TestCase):

    def test_needs_a_driver_started_with_bidi(self):
        previous = webdriver_wrapper_instance.current_webdriver
        try:
            webdriver_wrapper_instance.current_webdriver = None
            with self.assertRaises(BidiEventsError):
                SeleniumBidiEvents().route_mock("*/x", {})
            webdriver_wrapper_instance.current_webdriver = MagicMock(caps={})
            with self.assertRaises(BidiEventsError):
                SeleniumBidiEvents().start_har_recording()
        finally:
            webdriver_wrapper_instance.current_webdriver = previous


class TestRouteMocks(_BidiCase):

    def test_each_mock_is_an_intercept_on_its_pattern_with_one_listener(self):
        self.events.route_mock("*/api/a", {"body": "a"})
        self.events.route_mock_json("https://a.test/b", {"v": 1}, status=201)
        intercepts = _sent(self.driver, "network.addIntercept")
        self.assertEqual([params["urlPatterns"] for params in intercepts],
                         [[{"type": "pattern", "pathname": "/api/a"}],
                          [{"type": "string", "pattern": "https://a.test/b"}]])
        self.assertTrue(all(params["phases"] == ["beforeRequestSent"] for params in intercepts))
        self.assertEqual(_sent(self.driver, "session.subscribe"), [{"events": ["network.beforeRequestSent"]}])
        self.assertEqual(self.driver.network.conn.add_callback.call_count, 1)

    def test_blocked_request_on_our_intercept_gets_the_mock(self):
        self.events.route_mock("*/api/a", {"status": 404, "body": "gone", "headers": {"X-A": 1},
                                           "content_type": "text/plain"})
        self.events._on_request_sent({"isBlocked": True, "intercepts": ["i1"],
                                      "request": {"request": "r7", "url": "http://h/api/a"}})
        [provided] = _sent(self.driver, "network.provideResponse")
        self.assertEqual(provided["request"], "r7")
        self.assertEqual(provided["statusCode"], 404)
        self.assertEqual(provided["body"], {"type": "string", "value": "gone"})
        self.assertEqual({header["name"]: header["value"]["value"] for header in provided["headers"]},
                         {"X-A": "1", "Content-Type": "text/plain"})

    def test_the_newest_matching_mock_wins(self):
        self.events.route_mock("*/api/a", {"body": "old"})
        self.events.route_mock("*/api/a", {"body": "new"})
        self.events._on_request_sent({"isBlocked": True, "intercepts": ["i1", "i2"],
                                      "request": {"request": "r1"}})
        self.assertEqual(_sent(self.driver, "network.provideResponse")[0]["body"]["value"], "new")

    def test_requests_not_held_for_us_are_left_alone(self):
        self.events.route_mock("*/api/a", {"body": "a"})
        self.events._on_request_sent({"isBlocked": False, "intercepts": ["i1"], "request": {"request": "r1"}})
        self.events._on_request_sent({"isBlocked": True, "intercepts": ["other"], "request": {"request": "r2"}})
        self.assertEqual(_sent(self.driver, "network.provideResponse"), [])
        self.assertEqual(_sent(self.driver, "network.continueRequest"), [])

    def test_an_unusable_response_is_refused_when_registered(self):
        with self.assertRaises(BidiEventsError):
            self.events.route_mock("*/api/a", {"status": "teapot"})
        self.assertEqual(_sent(self.driver, "network.addIntercept"), [])

    def test_a_failed_answer_lets_the_request_continue(self):
        self.events.route_mock("*/api/a", {"body": "a"})

        def execute(command):
            if command[0] == "network.provideResponse":
                raise WebDriverException("no such request")
            return {}
        self.driver.network.conn.execute.side_effect = execute
        self.events._on_request_sent({"isBlocked": True, "intercepts": ["i1"], "request": {"request": "r1"}})
        self.assertEqual(_sent(self.driver, "network.continueRequest"), [{"request": "r1"}])

    def test_unmock_removes_that_pattern_and_clear_stops_listening(self):
        self.events.route_mock("*/api/a", {})
        self.events.route_mock("*/api/b", {})
        self.events.route_unmock("*/api/a")
        self.assertEqual(_sent(self.driver, "network.removeIntercept"), [{"intercept": "i1"}])
        self.assertEqual(_sent(self.driver, "session.unsubscribe"), [])
        self.events.route_clear()
        self.assertEqual(_sent(self.driver, "network.removeIntercept")[-1], {"intercept": "i2"})
        self.assertEqual(_sent(self.driver, "session.unsubscribe"), [{"events": ["network.beforeRequestSent"]}])
        self.driver.network.conn.remove_callback.assert_called_once()


class TestCaptureAndHar(_BidiCase):

    def test_capture_buffers_console_errors_responses_and_mutations(self):
        self.events.start_event_capture(dom_mutations=True)
        self.assertEqual(_sent(self.driver, "session.subscribe"),
                         [{"events": ["network.responseCompleted"]}, {"events": ["script.message"]}])
        self.events._on_console(MagicMock(level="info", text="hi"))
        self.events._on_javascript_error(MagicMock(text="boom"))
        self.events._on_response({"response": {"url": "http://h/x", "status": 503}, "request": {"method": "GET"}})
        self.events._on_script_message({"channel": selenium_events._DOM_CHANNEL,
                                        "data": {"value": json.dumps([{"type": "childList", "added": 1}])}})
        self.events._on_script_message({"channel": "someone-else", "data": {"value": "[1]"}})
        self.events._on_script_message({"channel": selenium_events._DOM_CHANNEL, "data": {"value": "{bad"}})
        self.assertEqual([(m["type"], m["text"]) for m in self.events.console_messages()],
                         [("info", "hi"), ("error", "boom")])
        self.assertEqual(self.events.network_responses()[0]["ok"], False)
        self.assertEqual(self.events.dom_mutation_records(), [{"type": "childList", "added": 1}])
        with self.assertRaises(EventCaptureError):
            self.events.capture.assert_no_5xx()
        self.events.stop_event_capture()
        self.assertEqual(len(_sent(self.driver, "session.unsubscribe")), 2)
        self.events.clear_event_capture()
        self.assertEqual(self.events.console_messages(), [])

    def test_har_pairs_requests_with_responses(self):
        self.events.start_har_recording()
        self.events._on_har_request({"timestamp": 1000, "request": {
            "request": "r1", "url": "http://h/", "method": "GET",
            "headers": [{"name": "Accept", "value": {"type": "string", "value": "*/*"}}]}})
        self.events._on_har_response({"timestamp": 1250, "request": {"request": "r1"}, "response": {
            "url": "http://h/", "status": 200, "statusText": "OK", "mimeType": "text/html"}})
        with tempfile.TemporaryDirectory() as tmp:
            har = Path(tmp) / "out" / "run.har"
            self.assertEqual(self.events.stop_har_recording(str(har)), str(har))
            [entry] = json.loads(har.read_text(encoding="utf-8"))["log"]["entries"]
        self.assertEqual(entry["request"]["url"], "http://h/")
        self.assertEqual(entry["request"]["headers"], [{"name": "Accept", "value": "*/*"}])
        self.assertEqual(entry["response"]["status"], 200)
        self.assertEqual(entry["time"], 250.0)
        self.assertEqual(len(_sent(self.driver, "session.unsubscribe")), 2)


class TestCommands(unittest.TestCase):

    def test_bidi_commands_are_registered(self):
        names = ("WR_event_capture_start", "WR_event_capture_stop", "WR_event_capture_clear",
                 "WR_console_messages", "WR_network_responses", "WR_dom_mutations",
                 "WR_assert_no_console_errors", "WR_assert_no_5xx", "WR_assert_no_4xx_or_5xx",
                 "WR_start_har_recording", "WR_stop_har_recording",
                 "WR_route_mock", "WR_route_mock_json", "WR_route_unmock", "WR_route_clear")
        for name in names:
            self.assertIn(name, executor.event_dict)


if __name__ == "__main__":
    unittest.main()
