"""Unit tests for je_web_runner.utils.failure_triage."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.ai_assist.llm_assist import set_llm_callable
from je_web_runner.utils.failure_bundle.bundle import FailureBundle
from je_web_runner.utils.failure_triage.triage import (
    FailureTriageError,
    TriageReport,
    TriageSignals,
    extract_signals_from_bundle,
    render_markdown,
    save_report,
    triage_bundle,
    triage_failure,
)


def _make_bundle(tmpdir: Path) -> Path:
    bundle = FailureBundle(
        test_name="checkout_test",
        error_repr="TimeoutException: locator #checkout-btn not found at line 123",
    )
    bundle.metadata["steps"] = [
        ["WR_to_url", {"url": "https://shop.example/cart"}],
        ["WR_element_click", {"locator": "#login"}],
        ["WR_element_input", {"locator": "#username", "text": "alice"}],
        ["WR_element_click", {"locator": "#checkout-btn"}],
    ]
    bundle.add_dom("<html><body><div id='checkout-disabled'>...</div></body></html>")
    bundle.add_console([
        {"level": "warning", "text": "Deprecation: foo"},
        {"level": "error", "text": "Uncaught TypeError"},
    ])
    bundle.add_network([
        {"url": "https://api.shop.example/cart", "status": 200},
        {"url": "https://api.shop.example/checkout", "status": 503},
    ])
    bundle.add_screenshot(b"\x89PNG\r\n\x1a\n" + b"x" * 16)
    return bundle.write(tmpdir / "bundle.zip")


class TestExtractSignals(unittest.TestCase):

    def test_extracts_from_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_bundle(Path(tmpdir))
            signals = extract_signals_from_bundle(path)
            self.assertEqual(signals.test_name, "checkout_test")
            self.assertIn("timeoutexception", signals.error_signature)
            self.assertNotIn("123", signals.error_signature)  # number normalised
            self.assertEqual(len(signals.last_steps), 4)
            self.assertEqual(signals.console_tail[-1]["level"], "error")
            self.assertEqual(signals.network_tail[-1]["status"], 503)
            self.assertIn("checkout-disabled", signals.dom_excerpt)
            self.assertTrue(signals.has_screenshot)

    def test_explicit_steps_override_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_bundle(Path(tmpdir))
            signals = extract_signals_from_bundle(
                path, steps=[["WR_quit_all"]], max_steps=5,
            )
            self.assertEqual(len(signals.last_steps), 1)
            self.assertEqual(signals.last_steps[0], ["WR_quit_all"])

    def test_tail_slicing_respects_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = FailureBundle(test_name="big", error_repr="boom")
            bundle.add_console([{"i": i} for i in range(50)])
            bundle.add_network([{"i": i} for i in range(50)])
            path = bundle.write(Path(tmpdir) / "b.zip")
            signals = extract_signals_from_bundle(
                path, max_console=5, max_network=3,
            )
            self.assertEqual(len(signals.console_tail), 5)
            self.assertEqual(signals.console_tail[0]["i"], 45)
            self.assertEqual(len(signals.network_tail), 3)
            self.assertEqual(signals.network_tail[0]["i"], 47)


class TestTriageFailure(unittest.TestCase):

    def setUp(self):
        self.signals = TriageSignals(
            test_name="checkout_test",
            error_repr="TimeoutException: locator missing",
            error_signature="timeoutexception: locator missing",
            last_steps=[["WR_element_click", {"locator": "#x"}]],
            console_tail=[{"level": "error", "text": "boom"}],
            network_tail=[{"url": "x", "status": 503}],
            dom_excerpt="<div></div>",
        )

    def tearDown(self):
        set_llm_callable(None)

    def test_parses_valid_payload(self):
        response = json.dumps({
            "likely_cause": "Locator changed",
            "category": "locator",
            "evidence": ["#x not present in DOM"],
            "next_steps": ["Inspect DOM", "Update selector"],
            "suggested_fix": "Change `#x` to `[data-testid=x]`",
            "confidence": 0.8,
        })
        set_llm_callable(lambda _prompt: response)
        report = triage_failure(self.signals)
        self.assertEqual(report.category, "locator")
        self.assertAlmostEqual(report.confidence, 0.8)
        self.assertEqual(report.next_steps, ["Inspect DOM", "Update selector"])
        self.assertEqual(report.test_name, "checkout_test")

    def test_no_callable_raises(self):
        set_llm_callable(None)
        with self.assertRaises(FailureTriageError):
            triage_failure(self.signals)

    def test_missing_keys_raises(self):
        set_llm_callable(lambda _p: json.dumps({"likely_cause": "x"}))
        with self.assertRaises(FailureTriageError):
            triage_failure(self.signals)

    def test_invalid_json_raises(self):
        set_llm_callable(lambda _p: "not json at all")
        with self.assertRaises(FailureTriageError):
            triage_failure(self.signals)

    def test_confidence_clamped(self):
        response = json.dumps({
            "likely_cause": "x", "category": "timing",
            "evidence": [], "next_steps": [], "confidence": 7.0,
        })
        set_llm_callable(lambda _p: response)
        report = triage_failure(self.signals)
        self.assertEqual(report.confidence, 1.0)

    def test_unknown_category_falls_through(self):
        response = json.dumps({
            "likely_cause": "x", "category": "alien",
            "evidence": [], "next_steps": [], "confidence": 0.5,
        })
        set_llm_callable(lambda _p: response)
        report = triage_failure(self.signals)
        self.assertEqual(report.category, "unknown")

    def test_evidence_string_is_coerced(self):
        response = json.dumps({
            "likely_cause": "x", "category": "timing",
            "evidence": "single string", "next_steps": [],
            "confidence": 0.3,
        })
        set_llm_callable(lambda _p: response)
        report = triage_failure(self.signals)
        self.assertEqual(report.evidence, ["single string"])


class TestTriageBundle(unittest.TestCase):

    def tearDown(self):
        set_llm_callable(None)

    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _make_bundle(Path(tmpdir))
            response = json.dumps({
                "likely_cause": "Backend 503 prevents checkout",
                "category": "network", "evidence": ["503 on /checkout"],
                "next_steps": ["Retry", "Check backend"],
                "suggested_fix": "Add retry middleware",
                "confidence": 0.7,
            })
            set_llm_callable(lambda _p: response)
            report = triage_bundle(path)
            self.assertEqual(report.category, "network")
            self.assertEqual(report.test_name, "checkout_test")


class TestRenderMarkdown(unittest.TestCase):

    def test_contains_required_sections(self):
        report = TriageReport(
            likely_cause="Locator drift",
            category="locator",
            evidence=["#x removed"],
            next_steps=["Update selector"],
            suggested_fix="use data-testid",
            confidence=0.9,
            test_name="t1",
            error_signature="sig",
        )
        md = render_markdown(report)
        self.assertIn("AI Failure Triage — t1", md)
        self.assertIn("90%", md)
        self.assertIn("Evidence", md)
        self.assertIn("Next steps", md)
        self.assertIn("Suggested fix", md)
        self.assertIn("`locator`", md)

    def test_handles_empty_sections(self):
        report = TriageReport(
            likely_cause="x", category="unknown",
            evidence=[], next_steps=[], suggested_fix="",
            confidence=0.1,
        )
        md = render_markdown(report)
        self.assertNotIn("Evidence", md)
        self.assertNotIn("Suggested fix", md)


class TestSaveReport(unittest.TestCase):

    def test_round_trips_json(self):
        report = TriageReport(
            likely_cause="x", category="data", evidence=["e"],
            next_steps=["s"], suggested_fix="f", confidence=0.5,
            test_name="t",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_report(report, Path(tmpdir) / "report.json")
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["likely_cause"], "x")
            self.assertEqual(payload["category"], "data")


if __name__ == "__main__":
    unittest.main()
