import unittest

from je_web_runner.utils.scheduler.cron_runner import (
    SchedulerError,
    ScheduledRunner,
    reset_scheduler,
    schedule,
    scheduler_counts,
    run_scheduler_for,
)


class TestScheduledRunner(unittest.TestCase):

    def test_add_rejects_zero_interval(self):
        runner = ScheduledRunner()
        with self.assertRaises(SchedulerError):
            runner.add("noop", 0, lambda: None)

    def test_run_for_invokes_callback_multiple_times(self):
        runner = ScheduledRunner()
        calls = []

        def tick():
            calls.append(1)

        runner.add("tick", 0.05, tick)
        runner.run_for(0.25)
        # at 0.05s interval over ~0.25s we expect at least 3 fires.
        self.assertGreaterEqual(len(calls), 3)
        self.assertEqual(runner.counts()["tick"], len(calls))

    def test_run_for_swallows_callback_exceptions(self):
        runner = ScheduledRunner()
        survived = []

        def boom():
            raise RuntimeError("boom")

        def survives():
            survived.append(1)

        runner.add("bad", 0.05, boom)
        runner.add("good", 0.05, survives)
        runner.run_for(0.2)
        # Even though one job raises, the scheduler keeps the other firing.
        self.assertGreater(len(survived), 0)


class TestModuleLevelHelpers(unittest.TestCase):

    def setUp(self):
        reset_scheduler()

    def tearDown(self):
        reset_scheduler()

    def test_schedule_then_run_for(self):
        ticks = []
        schedule("tick", 0.05, lambda: ticks.append(1))
        run_scheduler_for(0.2)
        self.assertGreater(scheduler_counts()["tick"], 0)


if __name__ == "__main__":
    unittest.main()
