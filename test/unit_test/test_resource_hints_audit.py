"""Unit tests for je_web_runner.utils.resource_hints_audit."""
import unittest

from je_web_runner.utils.resource_hints_audit.hints import (
    Hint,
    HintKind,
    ResourceHintsAuditError,
    assert_no_unused_hints,
    assert_origin_preconnected,
    assert_preload_has_as,
    find_unused_hints,
    parse_hints,
)


HTML = """
<link rel="preload" href="/hero.jpg" as="image">
<link rel="preconnect" href="https://cdn.example.com">
<link rel="prefetch" href="/next.html">
<link rel="preload" href="/broken.css">  <!-- no as= -->
"""


class TestParse(unittest.TestCase):

    def test_basic(self):
        hints = parse_hints(HTML)
        kinds = {h.kind for h in hints}
        self.assertIn(HintKind.PRELOAD, kinds)
        self.assertIn(HintKind.PRECONNECT, kinds)
        self.assertIn(HintKind.PREFETCH, kinds)

    def test_skip_unknown_rel(self):
        hints = parse_hints('<link rel="stylesheet" href="/x.css">')
        self.assertEqual(hints, [])

    def test_bad(self):
        with self.assertRaises(ResourceHintsAuditError):
            parse_hints(123)


class TestPreloadAs(unittest.TestCase):

    def test_pass(self):
        assert_preload_has_as([
            Hint(kind=HintKind.PRELOAD, href="/x.jpg", as_="image"),
        ])

    def test_fail(self):
        with self.assertRaises(ResourceHintsAuditError):
            assert_preload_has_as([
                Hint(kind=HintKind.PRELOAD, href="/x.css"),
            ])


class TestUnused(unittest.TestCase):

    def test_find(self):
        hints = parse_hints(HTML)
        unused = find_unused_hints(hints, used_urls=["/hero.jpg"])
        self.assertGreaterEqual(len(unused), 1)

    def test_assert_pass(self):
        assert_no_unused_hints(
            [Hint(kind=HintKind.PRELOAD, href="/x.jpg")],
            used_urls=["/x.jpg"],
        )

    def test_assert_fail(self):
        with self.assertRaises(ResourceHintsAuditError):
            assert_no_unused_hints(
                [Hint(kind=HintKind.PRELOAD, href="/x.jpg")],
                used_urls=["/other.jpg"],
            )


class TestPreconnect(unittest.TestCase):

    def test_pass(self):
        assert_origin_preconnected(
            [Hint(kind=HintKind.PRECONNECT, href="https://cdn.example.com")],
            origin="https://cdn.example.com",
        )

    def test_fail(self):
        with self.assertRaises(ResourceHintsAuditError):
            assert_origin_preconnected(
                [], origin="https://cdn.example.com",
            )

    def test_empty_origin(self):
        with self.assertRaises(ResourceHintsAuditError):
            assert_origin_preconnected([], origin="")


if __name__ == "__main__":
    unittest.main()
