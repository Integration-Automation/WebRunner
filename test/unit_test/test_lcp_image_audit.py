"""Unit tests for je_web_runner.utils.lcp_image_audit."""
import unittest

from je_web_runner.utils.lcp_image_audit.audit import (
    LcpCandidate,
    LcpImageAuditError,
    assert_fetchpriority_high,
    assert_lcp_not_lazy_loaded,
    assert_lcp_preloaded,
    parse_candidate,
)


class TestParse(unittest.TestCase):

    def test_basic(self):
        c = parse_candidate({"url": "/hero.jpg", "size_px": 1000})
        self.assertEqual(c.url, "/hero.jpg")

    def test_src_alias(self):
        c = parse_candidate({"src": "/x.jpg"})
        self.assertEqual(c.url, "/x.jpg")

    def test_missing_url(self):
        with self.assertRaises(LcpImageAuditError):
            parse_candidate({})

    def test_bad_payload(self):
        with self.assertRaises(LcpImageAuditError):
            parse_candidate("nope")


class TestPreloaded(unittest.TestCase):

    def test_pass(self):
        html = '<link rel="preload" href="/hero.jpg" as="image">'
        assert_lcp_preloaded(LcpCandidate(url="/hero.jpg"), html)

    def test_reverse_order(self):
        html = '<link as="image" href="/hero.jpg" rel="preload">'
        assert_lcp_preloaded(LcpCandidate(url="/hero.jpg"), html)

    def test_link_header(self):
        assert_lcp_preloaded(
            LcpCandidate(url="/hero.jpg"), "",
            link_header_urls=["/hero.jpg"],
        )

    def test_fail(self):
        with self.assertRaises(LcpImageAuditError):
            assert_lcp_preloaded(LcpCandidate(url="/missing.jpg"),
                                 '<link rel="preload" href="/hero.jpg" as="image">')

    def test_bad_html(self):
        with self.assertRaises(LcpImageAuditError):
            assert_lcp_preloaded(LcpCandidate(url="/x"), html=123)  # NOSONAR python:S5655 - deliberate bad input


class TestLazy(unittest.TestCase):

    def test_pass(self):
        assert_lcp_not_lazy_loaded(LcpCandidate(url="/hero.jpg"),
                                   '<img src="/hero.jpg">')

    def test_fail(self):
        with self.assertRaises(LcpImageAuditError):
            assert_lcp_not_lazy_loaded(
                LcpCandidate(url="/hero.jpg"),
                '<img src="/hero.jpg" loading="lazy">',
            )

    def test_bad_html(self):
        with self.assertRaises(LcpImageAuditError):
            assert_lcp_not_lazy_loaded(LcpCandidate(url="/x"), html=123)  # NOSONAR python:S5655 - deliberate bad input


class TestFetchPriority(unittest.TestCase):

    def test_pass(self):
        assert_fetchpriority_high(
            LcpCandidate(url="/hero.jpg"),
            '<img src="/hero.jpg" fetchpriority="high">',
        )

    def test_pass_reverse(self):
        assert_fetchpriority_high(
            LcpCandidate(url="/hero.jpg"),
            '<img fetchpriority="high" src="/hero.jpg">',
        )

    def test_fail(self):
        with self.assertRaises(LcpImageAuditError):
            assert_fetchpriority_high(
                LcpCandidate(url="/hero.jpg"),
                '<img src="/hero.jpg">',
            )

    def test_bad_html(self):
        with self.assertRaises(LcpImageAuditError):
            assert_fetchpriority_high(LcpCandidate(url="/x"), html=123)  # NOSONAR python:S5655 - deliberate bad input


if __name__ == "__main__":
    unittest.main()
