import re
import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.header_tampering import (
    HeaderRule,
    HeaderTampering,
    HeaderTamperingError,
)
from je_web_runner.utils.header_tampering.tamper import apply_to_request_headers


class TestHeaderRule(unittest.TestCase):

    def test_invalid_action_raises(self):
        with self.assertRaises(HeaderTamperingError):
            HeaderRule(name="x", header="X-Test", action="zap", value="y")

    def test_missing_value_raises(self):
        with self.assertRaises(HeaderTamperingError):
            HeaderRule(name="x", header="X-Test", action="set")

    def test_remove_no_value_ok(self):
        HeaderRule(name="x", header="X-Test", action="remove")


class TestApplyHeaders(unittest.TestCase):

    def test_set(self):
        rules = [HeaderRule(name="x", header="X-Test", action="set", value="1")]
        out = apply_to_request_headers({"a": "1"}, "https://example.com", rules)
        self.assertEqual(out["X-Test"], "1")

    def test_remove(self):
        rules = [HeaderRule(name="x", header="cookie", action="remove")]
        out = apply_to_request_headers({"cookie": "abc"}, "https://example.com", rules)
        self.assertNotIn("cookie", out)

    def test_append(self):
        rules = [HeaderRule(name="x", header="X-Trace", action="append", value="b")]
        out = apply_to_request_headers({"X-Trace": "a"}, "https://example.com", rules)
        self.assertEqual(out["X-Trace"], "a, b")

    def test_url_match_filter(self):
        rules = [HeaderRule(
            name="x", header="X-Test", action="set", value="1",
            url_match=re.compile("/api/"),
        )]
        applied = apply_to_request_headers({}, "https://example.com/api/x", rules)
        ignored = apply_to_request_headers({}, "https://example.com/static", rules)
        self.assertIn("X-Test", applied)
        self.assertNotIn("X-Test", ignored)


class TestHeaderTampering(unittest.TestCase):

    def test_attach_and_dispatch(self):
        page = MagicMock()
        ht = HeaderTampering()
        ht.set_header("X-Forwarded-For", "192.0.2.1")
        ht.remove_header("cookie")
        ht.attach_to_page(page)
        page.route.assert_called_once()
        # Invoke the handler directly
        handler = page.route.call_args.args[1]
        request = MagicMock(url="https://example.com/", headers={"cookie": "session=x"})
        route = MagicMock()
        handler(route, request)
        sent = route.continue_.call_args.kwargs["headers"]
        self.assertEqual(sent["X-Forwarded-For"], "192.0.2.1")
        self.assertNotIn("cookie", sent)

    def test_attach_to_non_playwright_raises(self):
        with self.assertRaises(HeaderTamperingError):
            HeaderTampering(rules=[]).attach_to_page(object())


if __name__ == "__main__":
    unittest.main()
