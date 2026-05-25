"""Unit tests for je_web_runner.utils.web_share_assert."""
import unittest

from je_web_runner.utils.web_share_assert.share import (
    FallbackEvent,
    INSTALL_SCRIPT,
    ShareCall,
    ShareLog,
    WebShareAssertError,
    assert_fallback_shown,
    assert_has_field,
    assert_shared,
    assert_url_origin,
    parse_log,
)


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("navigator.share", INSTALL_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        log = parse_log({
            "shares": [{"title": "t", "url": "https://x/", "filesCount": 0}],
            "fallbacks": [{"id": "btn"}],
        })
        self.assertEqual(log.shares[0].title, "t")
        self.assertEqual(log.fallbacks[0].id, "btn")

    def test_skip_non_dict(self):
        log = parse_log({"shares": ["x"]})
        self.assertEqual(log.shares, [])

    def test_bad_payload(self):
        with self.assertRaises(WebShareAssertError):
            parse_log("nope")


class TestShared(unittest.TestCase):

    def test_pass(self):
        s = assert_shared(ShareLog(shares=[ShareCall(title="t")]))
        self.assertEqual(s.title, "t")

    def test_fail(self):
        with self.assertRaises(WebShareAssertError):
            assert_shared(ShareLog())


class TestOrigin(unittest.TestCase):

    def test_pass(self):
        assert_url_origin(
            ShareLog(shares=[ShareCall(url="https://example.com/path")]),
            expected_origin="https://example.com",
        )

    def test_fail(self):
        with self.assertRaises(WebShareAssertError):
            assert_url_origin(
                ShareLog(shares=[ShareCall(url="https://other.com/")]),
                expected_origin="https://example.com",
            )

    def test_empty_origin(self):
        with self.assertRaises(WebShareAssertError):
            assert_url_origin(ShareLog(), expected_origin="")


class TestHasField(unittest.TestCase):

    def test_pass(self):
        assert_has_field(ShareLog(shares=[ShareCall(url="https://x/")]),
                         field="url")

    def test_fail(self):
        with self.assertRaises(WebShareAssertError):
            assert_has_field(ShareLog(shares=[ShareCall()]), field="url")

    def test_bad_field(self):
        with self.assertRaises(WebShareAssertError):
            assert_has_field(ShareLog(), field="weird")


class TestFallback(unittest.TestCase):

    def test_pass(self):
        assert_fallback_shown(ShareLog(fallbacks=[FallbackEvent(id="x")]))

    def test_fail(self):
        with self.assertRaises(WebShareAssertError):
            assert_fallback_shown(ShareLog())


if __name__ == "__main__":
    unittest.main()
