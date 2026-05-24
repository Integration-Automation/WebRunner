"""Unit tests for je_web_runner.utils.prompt_drift_monitor."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.prompt_drift_monitor.monitor import (
    Baseline,
    BaselineSample,
    DriftFinding,
    DriftReport,
    PromptDriftError,
    assert_no_drift,
    capture_baseline,
    check_drift,
    load_baseline,
    save_baseline,
)


def _fixed_embedder(vector):
    return lambda _text: list(vector)


def _by_text_embedder(text):
    """Embedding that depends on text content (for similarity drift)."""
    return [float(text.count("a")), float(text.count("b")), float(text.count("c"))]


class TestCaptureBaseline(unittest.TestCase):

    def test_basic_capture(self):
        baseline = capture_baseline(
            [{"id": "q1", "prompt": "hi"}, {"id": "q2", "prompt": "bye"}],
            _fixed_embedder([1.0, 0.0]),
            lambda p: f"answer to {p}",
        )
        self.assertEqual(len(baseline.samples), 2)
        self.assertEqual(baseline.samples[0].embedding, [1.0, 0.0])

    def test_empty_prompts_rejected(self):
        with self.assertRaises(PromptDriftError):
            capture_baseline([], _fixed_embedder([1.0]), lambda _: "x")

    def test_missing_id_or_prompt(self):
        with self.assertRaises(PromptDriftError):
            capture_baseline([{"id": "x"}], _fixed_embedder([1.0]), lambda _: "y")
        with self.assertRaises(PromptDriftError):
            capture_baseline([{"prompt": "x"}], _fixed_embedder([1.0]), lambda _: "y")

    def test_answerer_failure_wrapped(self):
        def boom(_):
            raise RuntimeError("rate limit")
        with self.assertRaises(PromptDriftError):
            capture_baseline([{"id": "x", "prompt": "y"}], _fixed_embedder([1.0]), boom)

    def test_anchors_captured(self):
        baseline = capture_baseline(
            [{"id": "q", "prompt": "hi",
              "must_include": ["disclaimer"], "must_exclude": ["competitor"]}],
            _fixed_embedder([1.0]),
            lambda _: "x",
        )
        self.assertEqual(baseline.samples[0].must_include, ["disclaimer"])
        self.assertEqual(baseline.samples[0].must_exclude, ["competitor"])


class TestPersistence(unittest.TestCase):

    def test_save_and_load_round_trip(self):
        baseline = capture_baseline(
            [{"id": "q", "prompt": "hi"}],
            _fixed_embedder([1.0, 2.0]),
            lambda _: "answer",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = save_baseline(baseline, Path(tmp) / "b.json")
            loaded = load_baseline(path)
            self.assertEqual(len(loaded.samples), 1)
            self.assertEqual(loaded.samples[0].embedding, [1.0, 2.0])

    def test_load_missing_file(self):
        with self.assertRaises(PromptDriftError):
            load_baseline("/no/such/file.json")

    def test_load_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(PromptDriftError):
                load_baseline(path)

    def test_load_missing_samples_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text(json.dumps({"captured_at": "x"}), encoding="utf-8")
            with self.assertRaises(PromptDriftError):
                load_baseline(path)

    def test_load_malformed_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.json"
            path.write_text(json.dumps(
                {"samples": [{"prompt_id": "x"}]}  # missing fields
            ), encoding="utf-8")
            with self.assertRaises(PromptDriftError):
                load_baseline(path)

    def test_save_rejects_non_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PromptDriftError):
                save_baseline("not baseline", Path(tmp) / "x.json")  # type: ignore[arg-type]


class TestCheckDrift(unittest.TestCase):

    def _baseline_for(self, prompts):
        return capture_baseline(prompts, _by_text_embedder, lambda p: f"aaa {p}")

    def test_clean_run(self):
        baseline = self._baseline_for([{"id": "q", "prompt": "hi"}])
        report = check_drift(
            baseline, _by_text_embedder,
            lambda p: f"aaa {p}",  # exact baseline reproduction
            similarity_threshold=0.99,
        )
        self.assertTrue(report.passed())

    def test_drift_detected(self):
        baseline = self._baseline_for([{"id": "q", "prompt": "hi"}])
        report = check_drift(
            baseline, _by_text_embedder,
            lambda _: "ccc",  # totally different vector
            similarity_threshold=0.9,
        )
        self.assertFalse(report.passed())
        self.assertTrue(report.findings[0].drifted)

    def test_missing_required(self):
        baseline = capture_baseline(
            [{"id": "q", "prompt": "hi", "must_include": ["disclaimer"]}],
            _by_text_embedder, lambda _: "disclaimer aaa",
        )
        report = check_drift(
            baseline, _by_text_embedder, lambda _: "aaa without it",
        )
        self.assertFalse(report.passed())
        self.assertIn("disclaimer", report.findings[0].missing_required)

    def test_forbidden_present(self):
        baseline = capture_baseline(
            [{"id": "q", "prompt": "hi", "must_exclude": ["competitor"]}],
            _by_text_embedder, lambda _: "aaa clean",
        )
        report = check_drift(
            baseline, _by_text_embedder, lambda _: "aaa with competitor mentioned",
        )
        self.assertIn("competitor", report.findings[0].forbidden_present)

    def test_bad_threshold(self):
        with self.assertRaises(PromptDriftError):
            check_drift(Baseline(), _by_text_embedder, lambda _: "x",
                        similarity_threshold=0.0)
        with self.assertRaises(PromptDriftError):
            check_drift(Baseline(), _by_text_embedder, lambda _: "x",
                        similarity_threshold=2.0)

    def test_answerer_failure(self):
        baseline = self._baseline_for([{"id": "q", "prompt": "hi"}])
        def boom(_):
            raise RuntimeError("down")
        with self.assertRaises(PromptDriftError):
            check_drift(baseline, _by_text_embedder, boom)

    def test_rejects_non_baseline(self):
        with self.assertRaises(PromptDriftError):
            check_drift("nope", _by_text_embedder, lambda _: "x")  # type: ignore[arg-type]


class TestAssertNoDrift(unittest.TestCase):

    def test_pass(self):
        assert_no_drift(DriftReport(threshold=0.9))

    def test_fail(self):
        report = DriftReport(
            threshold=0.9,
            findings=[DriftFinding(prompt_id="q", similarity=0.2, drifted=True)],
        )
        with self.assertRaises(PromptDriftError):
            assert_no_drift(report)

    def test_rejects_non_report(self):
        with self.assertRaises(PromptDriftError):
            assert_no_drift("not a report")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
