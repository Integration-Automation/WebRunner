"""Unit tests for je_web_runner.utils.third_party_block_test."""
import unittest

from je_web_runner.utils.third_party_block_test.block import (
    BlockOutcome,
    BlockReport,
    Resilience,
    ThirdPartyBlockError,
    Vendor,
    assert_resilient_to,
    builtin_vendors,
    run_block_matrix,
)


class TestBuiltin(unittest.TestCase):

    def test_has_common_vendors(self):
        names = {v.name for v in builtin_vendors()}
        for needed in ("google_analytics", "stripe", "hotjar", "segment"):
            self.assertIn(needed, names)

    def test_stripe_is_critical(self):
        stripe = next(v for v in builtin_vendors() if v.name == "stripe")
        self.assertTrue(stripe.critical_path)


class TestRunBlockMatrix(unittest.TestCase):

    def test_pass_for_all(self):
        applied = []
        report = run_block_matrix(
            [Vendor("a", ("*://a.com/*",)), Vendor("b", ("*://b.com/*",))],
            applied.append,
            lambda: None,
        )
        self.assertEqual(len(report.outcomes), 2)
        self.assertTrue(all(o.resilience == Resilience.RESILIENT for o in report.outcomes))
        # +1 unblock-all call
        self.assertEqual(len(applied), 3)

    def test_degraded_flow(self):
        report = run_block_matrix(
            [Vendor("x", ("*://x.com/*",))],
            lambda p: None,
            lambda: "slow render without telemetry",
        )
        self.assertEqual(report.outcomes[0].resilience, Resilience.DEGRADED)

    def test_broken_flow(self):
        def boom():
            raise RuntimeError("checkout button stuck")
        report = run_block_matrix(
            [Vendor("x", ("*://x.com/*",))],
            lambda p: None,
            boom,
        )
        self.assertEqual(report.outcomes[0].resilience, Resilience.BROKEN)
        self.assertEqual(len(report.broken()), 1)

    def test_empty_vendors(self):
        with self.assertRaises(ThirdPartyBlockError):
            run_block_matrix([], lambda p: None, lambda: None)

    def test_non_callable_block(self):
        with self.assertRaises(ThirdPartyBlockError):
            run_block_matrix([Vendor("x", ("*",))], "nope", lambda: None)

    def test_cdp_failure_wrapped(self):
        def bad(p):
            raise RuntimeError("cdp down")
        with self.assertRaises(ThirdPartyBlockError):
            run_block_matrix([Vendor("x", ("*",))], bad, lambda: None)


class TestAssertResilient(unittest.TestCase):

    def test_pass(self):
        report = BlockReport(outcomes=[
            BlockOutcome(vendor="a", resilience=Resilience.RESILIENT),
            BlockOutcome(vendor="b", resilience=Resilience.DEGRADED),
        ])
        assert_resilient_to(report, vendors=["a", "b"])

    def test_fail(self):
        report = BlockReport(outcomes=[
            BlockOutcome(vendor="a", resilience=Resilience.BROKEN),
        ])
        with self.assertRaises(ThirdPartyBlockError):
            assert_resilient_to(report, vendors=["a"])


class TestToDict(unittest.TestCase):

    def test_resilience_value(self):
        o = BlockOutcome(vendor="a", resilience=Resilience.RESILIENT)
        self.assertEqual(o.to_dict()["resilience"], "resilient")


if __name__ == "__main__":
    unittest.main()
