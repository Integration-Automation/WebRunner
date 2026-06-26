"""Unit tests for je_web_runner.utils.failure_auto_tag."""
import unittest

from je_web_runner.utils.failure_auto_tag.tag import (
    FailureAutoTagError,
    FailureBundle,
    Tag,
    assert_tagged_with,
    heuristic_tags,
    llm_tags,
    merge_tags,
)


class TestHeuristic(unittest.TestCase):

    def test_flaky_locator(self):
        b = FailureBundle(exception_text="NoSuchElement: foo")
        tags = heuristic_tags(b)
        self.assertIn("flaky-locator", [t.name for t in tags])

    def test_stale_element(self):
        b = FailureBundle(exception_text="StaleElement reference exception")
        self.assertIn("selector-stale", [t.name for t in heuristic_tags(b)])

    def test_timeout(self):
        b = FailureBundle(exception_text="TimeoutException: 10s")
        self.assertIn("timeout", [t.name for t in heuristic_tags(b)])

    def test_click_intercepted(self):
        b = FailureBundle(
            exception_text="ElementClickInterceptedException",
        )
        self.assertIn("click-intercepted", [t.name for t in heuristic_tags(b)])

    def test_session_lost(self):
        b = FailureBundle(exception_text="invalid session id")
        self.assertIn("session-lost", [t.name for t in heuristic_tags(b)])

    def test_assertion(self):
        b = FailureBundle(exception_text="AssertionError: expected 1 got 2")
        self.assertIn("assertion-failed", [t.name for t in heuristic_tags(b)])

    def test_network_5xx(self):
        b = FailureBundle(
            exception_text="x", last_action="click",
            network_errors=[{"url": "/api", "status": 503}],
        )
        self.assertIn("network-5xx", [t.name for t in heuristic_tags(b)])

    def test_network_4xx(self):
        b = FailureBundle(
            exception_text="x",
            network_errors=[{"url": "/api", "status": 404}],
        )
        self.assertIn("network-4xx", [t.name for t in heuristic_tags(b)])

    def test_js_error(self):
        b = FailureBundle(
            exception_text="x",
            console_errors=["Uncaught TypeError: foo is not a function"],
        )
        self.assertIn("js-error", [t.name for t in heuristic_tags(b)])

    def test_empty_bundle_rejected(self):
        with self.assertRaises(FailureAutoTagError):
            heuristic_tags(FailureBundle())

    def test_bad_type(self):
        with self.assertRaises(FailureAutoTagError):
            heuristic_tags("nope")


class TestLlmTags(unittest.TestCase):

    def test_basic(self):
        def tagger(_):
            return [{"name": "ai-flake", "confidence": 0.8, "reason": "x"}]
        tags = llm_tags(FailureBundle(exception_text="x"), tagger)
        self.assertEqual(tags[0].name, "ai-flake")

    def test_non_callable(self):
        with self.assertRaises(FailureAutoTagError):
            llm_tags(FailureBundle(), "nope")

    def test_bad_return(self):
        with self.assertRaises(FailureAutoTagError):
            llm_tags(FailureBundle(), lambda b: "nope")

    def test_propagates_tagger_error(self):
        def boom(_bundle):
            raise RuntimeError("boom")
        with self.assertRaises(FailureAutoTagError):
            llm_tags(FailureBundle(), boom)

    def test_skips_malformed_items(self):
        tags = llm_tags(FailureBundle(),
                        lambda b: ["str-not-dict",
                                   {"name": ""},  # empty name
                                   {"name": "ok", "confidence": 0.5}])
        self.assertEqual([t.name for t in tags], ["ok"])

    def test_explicit_zero_confidence_preserved(self):
        tags = llm_tags(FailureBundle(),
                        lambda b: [{"name": "weak", "confidence": 0}])
        self.assertEqual(tags[0].confidence, 0.0)

    def test_missing_confidence_defaults_half(self):
        tags = llm_tags(FailureBundle(), lambda b: [{"name": "x"}])
        self.assertEqual(tags[0].confidence, 0.5)

    def test_non_numeric_confidence_defaults_half(self):
        tags = llm_tags(FailureBundle(),
                        lambda b: [{"name": "x", "confidence": "high"}])
        self.assertEqual(tags[0].confidence, 0.5)


class TestMerge(unittest.TestCase):

    def test_dedupe_keeps_highest(self):
        tags = merge_tags(
            [Tag("a", 0.5, "low")],
            [Tag("a", 0.9, "high"), Tag("b", 0.6)],
        )
        a = next(t for t in tags if t.name == "a")
        self.assertEqual(a.confidence, 0.9)


class TestAssert(unittest.TestCase):

    def test_pass(self):
        assert_tagged_with([Tag("x")], expected="x")

    def test_fail(self):
        with self.assertRaises(FailureAutoTagError):
            assert_tagged_with([Tag("a")], expected="x")


if __name__ == "__main__":
    unittest.main()
