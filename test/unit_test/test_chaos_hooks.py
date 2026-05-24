"""Unit tests for je_web_runner.utils.chaos_hooks."""
import unittest

from je_web_runner.utils.chaos_hooks.chaos import (
    ChaosEvent,
    ChaosFaultType,
    ChaosHooksError,
    ChaosPlan,
    ChaosRunner,
    plan_chaos,
    run_with_chaos,
)


STEPS = [f"step_{i}" for i in range(10)]


class TestPlan(unittest.TestCase):

    def test_seed_reproducible(self):
        a = plan_chaos(STEPS, fault_rate=0.5, seed=42)
        b = plan_chaos(STEPS, fault_rate=0.5, seed=42)
        self.assertEqual(
            [(e.step_index, e.fault) for e in a.events],
            [(e.step_index, e.fault) for e in b.events],
        )

    def test_zero_rate_yields_no_events(self):
        plan = plan_chaos(STEPS, fault_rate=0.0, seed=1)
        self.assertEqual(plan.events, [])

    def test_full_rate_excludes_skipped(self):
        plan = plan_chaos(STEPS, fault_rate=1.0, skip_first=2, skip_last=2, seed=0)
        # Indices 0,1,8,9 are skipped
        indexes = {e.step_index for e in plan.events}
        self.assertTrue(indexes.issubset({2, 3, 4, 5, 6, 7}))
        self.assertEqual(sorted(plan.skipped), [0, 1, 8, 9])

    def test_max_events_caps(self):
        plan = plan_chaos(STEPS, fault_rate=1.0, max_events=2, seed=0)
        self.assertLessEqual(len(plan.events), 2)

    def test_bad_rate_rejected(self):
        with self.assertRaises(ChaosHooksError):
            plan_chaos(STEPS, fault_rate=1.5)
        with self.assertRaises(ChaosHooksError):
            plan_chaos(STEPS, fault_rate=-0.1)

    def test_empty_faults_rejected(self):
        with self.assertRaises(ChaosHooksError):
            plan_chaos(STEPS, faults=[])

    def test_bad_skip_rejected(self):
        with self.assertRaises(ChaosHooksError):
            plan_chaos(STEPS, skip_first=-1)

    def test_describe_empty(self):
        self.assertIn("no chaos", plan_chaos(STEPS, fault_rate=0.0).describe())

    def test_describe_nonempty(self):
        plan = plan_chaos(STEPS, fault_rate=1.0, max_events=1, seed=0)
        self.assertIn("step", plan.describe())

    def test_faults_for_step(self):
        plan = ChaosPlan(events=[
            ChaosEvent(2, "a", ChaosFaultType.NETWORK_OFFLINE),
            ChaosEvent(2, "a", ChaosFaultType.CPU_THROTTLE),
            ChaosEvent(3, "b", ChaosFaultType.NETWORK_SLOW),
        ])
        self.assertEqual(len(plan.faults_for_step(2)), 2)
        self.assertEqual(len(plan.faults_for_step(3)), 1)
        self.assertEqual(plan.faults_for_step(99), [])


class TestRunner(unittest.TestCase):

    def test_runner_requires_chaos_plan(self):
        with self.assertRaises(ChaosHooksError):
            ChaosRunner(plan="not a plan")  # type: ignore[arg-type]

    def test_missing_injector_raises(self):
        plan = ChaosPlan(events=[ChaosEvent(0, "a", ChaosFaultType.CPU_THROTTLE)])
        with self.assertRaises(ChaosHooksError):
            ChaosRunner(plan=plan, injectors={})

    def test_missing_injector_warning_only(self):
        plan = ChaosPlan(events=[ChaosEvent(0, "a", ChaosFaultType.CPU_THROTTLE)])
        runner = ChaosRunner(plan=plan, injectors={}, raise_on_missing=False)
        self.assertEqual(runner.before_step(0, "a"), [])

    def test_before_step_fires_injectors(self):
        called: list = []
        plan = ChaosPlan(events=[
            ChaosEvent(0, "a", ChaosFaultType.NETWORK_OFFLINE),
            ChaosEvent(1, "b", ChaosFaultType.CPU_THROTTLE),
        ])
        runner = ChaosRunner(plan=plan, injectors={
            ChaosFaultType.NETWORK_OFFLINE: lambda e: called.append(("off", e.step_index)),
            ChaosFaultType.CPU_THROTTLE: lambda e: called.append(("cpu", e.step_index)),
        })
        runner.before_step(0, "a")
        runner.before_step(1, "b")
        self.assertEqual(called, [("off", 0), ("cpu", 1)])

    def test_before_step_propagates_injector_error(self):
        def boom(_):
            raise RuntimeError("kaboom")
        plan = ChaosPlan(events=[ChaosEvent(0, "a", ChaosFaultType.NETWORK_OFFLINE)])
        runner = ChaosRunner(plan=plan, injectors={ChaosFaultType.NETWORK_OFFLINE: boom})
        with self.assertRaises(ChaosHooksError):
            runner.before_step(0, "a")


class TestRunWithChaos(unittest.TestCase):

    def test_executes_steps_and_fires_chaos(self):
        executed: list = []
        injected: list = []
        plan = ChaosPlan(events=[
            ChaosEvent(2, "step_2", ChaosFaultType.NETWORK_OFFLINE),
        ])
        injectors = {
            ChaosFaultType.NETWORK_OFFLINE: lambda e: injected.append(e.step_index),
        }
        fired = run_with_chaos(
            STEPS,
            lambda i, name: executed.append(i),
            plan=plan,
            injectors=injectors,
        )
        self.assertEqual(executed, list(range(len(STEPS))))
        self.assertEqual(injected, [2])
        self.assertEqual(len(fired), 1)


if __name__ == "__main__":
    unittest.main()
