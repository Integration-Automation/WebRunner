"""Unit tests for je_web_runner.utils.hsts_preload_audit."""
import unittest

from je_web_runner.utils.hsts_preload_audit.audit import (
    HstsPreloadAuditError,
    assert_preload_ready,
    assert_served_over_https,
    parse_header,
)


GOOD = "max-age=63072000; includeSubDomains; preload"


class TestParse(unittest.TestCase):

    def test_basic(self):
        h = parse_header(GOOD)
        self.assertEqual(h.max_age, 63072000)
        self.assertTrue(h.include_subdomains)
        self.assertTrue(h.preload)

    def test_empty(self):
        with self.assertRaises(HstsPreloadAuditError):
            parse_header("")

    def test_bad_max_age(self):
        with self.assertRaises(HstsPreloadAuditError):
            parse_header("max-age=garbage")

    def test_partial(self):
        h = parse_header("max-age=100")
        self.assertEqual(h.max_age, 100)
        self.assertFalse(h.preload)


class TestPreloadReady(unittest.TestCase):

    def test_pass(self):
        assert_preload_ready(parse_header(GOOD))

    def test_short_max_age(self):
        with self.assertRaises(HstsPreloadAuditError):
            assert_preload_ready(
                parse_header("max-age=86400; includeSubDomains; preload"),
            )

    def test_missing_subdomain(self):
        with self.assertRaises(HstsPreloadAuditError):
            assert_preload_ready(parse_header("max-age=63072000; preload"))

    def test_missing_preload(self):
        with self.assertRaises(HstsPreloadAuditError):
            assert_preload_ready(parse_header(
                "max-age=63072000; includeSubDomains",
            ))


class TestHttps(unittest.TestCase):

    def test_pass(self):
        assert_served_over_https("https")

    def test_fail(self):
        with self.assertRaises(HstsPreloadAuditError):
            assert_served_over_https("http")

    def test_bad_type(self):
        with self.assertRaises(HstsPreloadAuditError):
            assert_served_over_https(123)
  # NOSONAR python:S5655 - deliberate bad input

if __name__ == "__main__":
    unittest.main()
