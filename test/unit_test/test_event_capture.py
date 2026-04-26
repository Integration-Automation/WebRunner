import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.observability.event_capture import (
    EventCapture,
    EventCaptureError,
)


def _console_message(message_type: str, text: str):
    msg = MagicMock()
    msg.type = message_type
    msg.text = text
    msg.location = {"url": "u"}
    return msg


def _response(url: str, status: int, method: str = "GET"):
    resp = MagicMock()
    resp.url = url
    resp.status = status
    resp.ok = status < 400
    resp.request.method = method
    return resp


class TestEventCapture(unittest.TestCase):

    def test_attach_registers_listeners(self):
        capture = EventCapture()
        page = MagicMock()
        capture.attach(page)
        # two .on(...) registrations: console + response
        self.assertEqual(page.on.call_count, 2)

    def test_console_and_response_buffered(self):
        capture = EventCapture()
        page = MagicMock()
        capture.attach(page)
        capture._on_console(_console_message("log", "hi"))
        capture._on_console(_console_message("error", "boom"))
        capture._on_response(_response("https://e.com/api", 500))
        capture._on_response(_response("https://e.com/img", 200))
        self.assertEqual(len(capture.console_messages), 2)
        self.assertEqual(len(capture.network_responses), 2)
        self.assertEqual(capture.console_messages[1]["type"], "error")

    def test_assert_no_console_errors(self):
        capture = EventCapture()
        capture.attach(MagicMock())
        capture._on_console(_console_message("log", "ok"))
        capture.assert_no_console_errors()
        capture._on_console(_console_message("error", "boom"))
        with self.assertRaises(EventCaptureError):
            capture.assert_no_console_errors()

    def test_assert_no_5xx(self):
        capture = EventCapture()
        capture.attach(MagicMock())
        capture._on_response(_response("u", 200))
        capture.assert_no_5xx()
        capture._on_response(_response("u", 503))
        with self.assertRaises(EventCaptureError):
            capture.assert_no_5xx()

    def test_assert_no_4xx_or_5xx(self):
        capture = EventCapture()
        capture.attach(MagicMock())
        capture._on_response(_response("u", 404))
        with self.assertRaises(EventCaptureError):
            capture.assert_no_4xx_or_5xx()

    def test_clear_resets_buffers(self):
        capture = EventCapture()
        capture.attach(MagicMock())
        capture._on_console(_console_message("log", "x"))
        capture.clear()
        self.assertEqual(capture.console_messages, [])

    def test_detach_removes_listeners(self):
        capture = EventCapture()
        page = MagicMock()
        capture.attach(page)
        capture.detach()
        self.assertEqual(page.remove_listener.call_count, 2)


if __name__ == "__main__":
    unittest.main()
