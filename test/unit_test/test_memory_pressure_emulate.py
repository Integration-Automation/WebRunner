"""Unit tests for je_web_runner.utils.memory_pressure_emulate."""
import unittest

from je_web_runner.utils.memory_pressure_emulate.emulate import (
    DEFAULT_PROFILES,
    EmulationProfile,
    MemoryPressureError,
    PressureRunOutcome,
    assert_passed_under_pressure,
    cdp_payloads,
    run_under_profile,
)


class TestProfile(unittest.TestCase):

    def test_validation(self):
        with self.assertRaises(MemoryPressureError):
            EmulationProfile(name="x", hardware_concurrency=0)
        with self.assertRaises(MemoryPressureError):
            EmulationProfile(name="x", cpu_throttle_rate=0.5)
        with self.assertRaises(MemoryPressureError):
            EmulationProfile(name="x", js_heap_limit_bytes=0)

    def test_defaults(self):
        names = {p.name for p in DEFAULT_PROFILES}
        self.assertIn("low_end_phone", names)
        self.assertIn("critical_pressure", names)


class TestCdpPayloads(unittest.TestCase):

    def test_basic(self):
        cmds = cdp_payloads(EmulationProfile(name="x"))
        methods = [c["method"] for c in cmds]
        self.assertIn("Emulation.setHardwareConcurrencyOverride", methods)
        self.assertIn("Emulation.setCPUThrottlingRate", methods)
        self.assertIn("Memory.simulatePressureNotification", methods)

    def test_includes_heap_when_set(self):
        cmds = cdp_payloads(EmulationProfile(name="x", js_heap_limit_bytes=1024))
        self.assertTrue(any(
            c["method"] == "HeapProfiler.setSamplingHeapProfiler" for c in cmds
        ))

    def test_rejects_non_profile(self):
        with self.assertRaises(MemoryPressureError):
            cdp_payloads("nope")


class TestRunUnderProfile(unittest.TestCase):

    def test_pass(self):
        sent = []

        def fake_cdp(method, params):
            sent.append(method)

        outcome = run_under_profile(
            EmulationProfile(name="x"), fake_cdp, lambda: None,
        )
        self.assertTrue(outcome.passed)
        self.assertIn("Emulation.setCPUThrottlingRate", sent)

    def test_test_failure_recorded(self):
        def bad():
            raise AssertionError("oops")
        outcome = run_under_profile(
            EmulationProfile(name="x"), lambda m, p: None, bad,
        )
        self.assertFalse(outcome.passed)
        self.assertIn("oops", outcome.error or "")

    def test_cdp_failure_wrapped(self):
        def bad_cdp(method, params):
            raise RuntimeError("no cdp")
        with self.assertRaises(MemoryPressureError):
            run_under_profile(EmulationProfile(name="x"), bad_cdp, lambda: None)

    def test_rejects_non_callable(self):
        with self.assertRaises(MemoryPressureError):
            run_under_profile(EmulationProfile(name="x"), "not", lambda: None)
        with self.assertRaises(MemoryPressureError):
            run_under_profile(EmulationProfile(name="x"), lambda m, p: None, "not")


class TestAssertPassed(unittest.TestCase):

    def test_pass(self):
        assert_passed_under_pressure(PressureRunOutcome(profile="x", passed=True))

    def test_fail(self):
        with self.assertRaises(MemoryPressureError):
            assert_passed_under_pressure(PressureRunOutcome(
                profile="x", passed=False, error="boom",
            ))

    def test_rejects_non_outcome(self):
        with self.assertRaises(MemoryPressureError):
            assert_passed_under_pressure("nope")


if __name__ == "__main__":
    unittest.main()
