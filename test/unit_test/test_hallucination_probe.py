"""Unit tests for je_web_runner.utils.hallucination_probe."""
import unittest

from je_web_runner.utils.hallucination_probe.probe import (
    HallucinationProbeError,
    Probe,
    ProbeReport,
    ProbeResult,
    assert_hallucination_rate_under,
    run_probes,
)


class TestProbeInit(unittest.TestCase):

    def test_basic(self):
        Probe(name="x", prompt="y", expected_substrings=["z"])

    def test_no_constraints(self):
        with self.assertRaises(HallucinationProbeError):
            Probe(name="x", prompt="y")

    def test_empty_name(self):
        with self.assertRaises(HallucinationProbeError):
            Probe(name="", prompt="y", expected_substrings=["z"])


class TestEvaluate(unittest.TestCase):

    def test_expected_hit(self):
        report = run_probes(
            [Probe(name="capital", prompt="?",
                   expected_substrings=["Paris"])],
            caller=lambda q: "The capital is Paris.",
        )
        self.assertTrue(report.results[0].passed)

    def test_expected_miss(self):
        report = run_probes(
            [Probe(name="capital", prompt="?",
                   expected_substrings=["Paris"])],
            caller=lambda q: "Berlin",
        )
        self.assertFalse(report.results[0].passed)

    def test_forbidden_hit(self):
        report = run_probes(
            [Probe(name="redact", prompt="?",
                   forbidden_substrings=["SSN"])],
            caller=lambda q: "Your SSN is 123",
        )
        self.assertFalse(report.results[0].passed)

    def test_expect_refusal_pass(self):
        report = run_probes(
            [Probe(name="unknown", prompt="?", expect_refusal=True)],
            caller=lambda q: "I don't know.",
        )
        self.assertTrue(report.results[0].passed)

    def test_expect_refusal_fail(self):
        report = run_probes(
            [Probe(name="unknown", prompt="?", expect_refusal=True)],
            caller=lambda q: "The answer is 42",
        )
        self.assertFalse(report.results[0].passed)


class TestRun(unittest.TestCase):

    def test_caller_raises(self):
        def boom(q):
            raise RuntimeError("net")
        report = run_probes(
            [Probe(name="p", prompt="?", expected_substrings=["x"])],
            caller=boom,
        )
        self.assertFalse(report.results[0].passed)

    def test_caller_returns_non_str(self):
        report = run_probes(
            [Probe(name="p", prompt="?", expected_substrings=["x"])],
            caller=lambda q: 123,
        )
        self.assertFalse(report.results[0].passed)

    def test_empty_probes(self):
        with self.assertRaises(HallucinationProbeError):
            run_probes([], caller=lambda q: "")

    def test_non_callable(self):
        with self.assertRaises(HallucinationProbeError):
            run_probes(
                [Probe(name="p", prompt="?", expected_substrings=["x"])],
                caller="nope",
            )


class TestRate(unittest.TestCase):

    def test_zero(self):
        self.assertEqual(ProbeReport().hallucination_rate, 0)

    def test_compute(self):
        report = ProbeReport(results=[
            ProbeResult(name="a", answer="", passed=True),
            ProbeResult(name="b", answer="", passed=False),
        ])
        self.assertEqual(report.hallucination_rate, 0.5)


class TestAssert(unittest.TestCase):

    def test_pass(self):
        assert_hallucination_rate_under(ProbeReport(), max_rate=0.1)

    def test_fail(self):
        report = ProbeReport(results=[
            ProbeResult(name="x", answer="", passed=False),
        ])
        with self.assertRaises(HallucinationProbeError):
            assert_hallucination_rate_under(report, max_rate=0)

    def test_bad_rate(self):
        with self.assertRaises(HallucinationProbeError):
            assert_hallucination_rate_under(ProbeReport(), max_rate=2)


if __name__ == "__main__":
    unittest.main()
