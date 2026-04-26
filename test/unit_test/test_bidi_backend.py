import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.bidi_backend import (
    BidiBackendError,
    BidiBridge,
    BidiEvent,
)


class TestDetect(unittest.TestCase):

    def test_detects_selenium(self):
        target = MagicMock()
        target.current_url = "https://x.com"
        # MagicMock auto-creates attributes; ensure both exist
        _ = target.script
        bridge = BidiBridge()
        self.assertEqual(bridge.detect_backend(target), "selenium")

    def test_detects_playwright(self):
        target = MagicMock(spec=["on", "remove_listener"])
        bridge = BidiBridge()
        self.assertEqual(bridge.detect_backend(target), "playwright")

    def test_unknown_target_raises(self):
        with self.assertRaises(BidiBackendError):
            BidiBridge().detect_backend(object())


class TestPlaywrightSubscribe(unittest.TestCase):

    def test_console_subscription_routes_event(self):
        page = MagicMock()
        bridge = BidiBridge()
        captured = []
        sub = bridge.subscribe(
            page, "console", captured.append, backend="playwright",
        )
        adapter = page.on.call_args.args[1]
        message = MagicMock()
        message.type = "log"
        message.text = "hello"
        adapter(message)
        self.assertEqual(len(captured), 1)
        evt = captured[0]
        self.assertIsInstance(evt, BidiEvent)
        self.assertEqual(evt.name, "console")
        self.assertEqual(evt.payload["text"], "hello")
        bridge.unsubscribe(sub)
        page.remove_listener.assert_called_once()

    def test_response_subscription_extracts_url_and_status(self):
        page = MagicMock()
        bridge = BidiBridge()
        captured = []
        bridge.subscribe(page, "response", captured.append, backend="playwright")
        adapter = page.on.call_args.args[1]
        response = MagicMock(url="/api/x", status=200)
        adapter(response)
        self.assertEqual(captured[0].payload["status"], 200)


class TestSeleniumSubscribe(unittest.TestCase):

    def test_console_translator_fails_when_method_missing(self):
        target = MagicMock(spec=["script", "current_url"])
        target.script = MagicMock(spec=[])
        bridge = BidiBridge()
        with self.assertRaises(BidiBackendError):
            bridge.subscribe(target, "console", lambda _e: None, backend="selenium")

    def test_console_translator_routes_handle(self):
        target = MagicMock()
        # Provide both methods
        target.script.add_console_message_handler.return_value = "handle-1"
        target.current_url = "https://x.com"
        bridge = BidiBridge()
        captured = []
        sub = bridge.subscribe(target, "console", captured.append, backend="selenium")
        adapter = target.script.add_console_message_handler.call_args.args[0]
        msg = MagicMock(type="error", text="boom")
        adapter(msg)
        self.assertEqual(captured[0].payload["text"], "boom")
        bridge.unsubscribe(sub)
        target.script.remove_console_message_handler.assert_called_once_with("handle-1")


class TestUnknownEvent(unittest.TestCase):

    def test_unsupported_event_raises(self):
        page = MagicMock()
        bridge = BidiBridge()
        with self.assertRaises(BidiBackendError):
            bridge.subscribe(page, "weird-event", lambda _e: None, backend="playwright")

    def test_register_translator_extends(self):
        page = MagicMock()
        bridge = BidiBridge()

        def custom(target, callback):
            return lambda: None

        bridge.register_translator("playwright", "weird-event", custom)
        sub = bridge.subscribe(page, "weird-event", lambda _e: None, backend="playwright")
        self.assertIn(sub, bridge.active_subscriptions())


class TestUnsubscribeAll(unittest.TestCase):

    def test_clears_subscriptions(self):
        page = MagicMock()
        bridge = BidiBridge()
        bridge.subscribe(page, "console", lambda _e: None, backend="playwright")
        bridge.subscribe(page, "response", lambda _e: None, backend="playwright")
        bridge.unsubscribe_all()
        self.assertEqual(bridge.active_subscriptions(), [])


if __name__ == "__main__":
    unittest.main()
