import unittest

from je_web_runner.utils.synthetic_monitoring import (
    SyntheticMonitor,
    SyntheticMonitorError,
)
from je_web_runner.utils.synthetic_monitoring.monitor import from_action_files


class TestSyntheticMonitor(unittest.TestCase):

    def test_register_and_tick_green(self):
        alerts = []
        monitor = SyntheticMonitor(alert_sink=alerts.append)
        monitor.register("homepage", lambda: None)
        results = monitor.tick_once()
        self.assertEqual(results[0].status, "green")
        # First green = no transition (initial state)
        self.assertEqual(alerts, [])

    def test_red_alert_on_failure_threshold(self):
        alerts = []
        monitor = SyntheticMonitor(alert_sink=alerts.append)

        def boom() -> None:
            raise RuntimeError("nope")

        monitor.register("svc", boom, failure_threshold=2)
        monitor.tick_once()
        self.assertEqual(alerts, [])  # first failure under threshold
        monitor.tick_once()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["current"], "red")

    def test_recovery_alert(self):
        alerts = []
        outcomes = iter([RuntimeError("a"), RuntimeError("b"), None, None])
        def check():
            value = next(outcomes)
            if isinstance(value, BaseException):
                raise value
        monitor = SyntheticMonitor(alert_sink=alerts.append)
        monitor.register("svc", check, failure_threshold=2, recovery_threshold=1)
        monitor.tick_once()  # fail #1
        monitor.tick_once()  # fail #2 -> red alert
        monitor.tick_once()  # success #1 -> recovery alert
        statuses = [a["current"] for a in alerts]
        self.assertEqual(statuses, ["red", "green"])

    def test_run_for_emits_per_iteration_results(self):
        monitor = SyntheticMonitor(alert_sink=lambda _payload: None)
        monitor.register("ok", lambda: None)
        results = monitor.run_for(
            iterations=3, interval_seconds=0,
            sleep=lambda _seconds: None,
        )
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.status == "green" for r in results))

    def test_invalid_register_args(self):
        monitor = SyntheticMonitor(alert_sink=lambda _payload: None)
        with self.assertRaises(SyntheticMonitorError):
            monitor.register("", lambda: None)
        with self.assertRaises(SyntheticMonitorError):
            monitor.register("x", "not callable")  # type: ignore[arg-type]
        with self.assertRaises(SyntheticMonitorError):
            monitor.register("x", lambda: None, failure_threshold=0)

    def test_invalid_alert_sink(self):
        with self.assertRaises(SyntheticMonitorError):
            SyntheticMonitor(alert_sink="not callable")  # type: ignore[arg-type]

    def test_run_for_invalid_iterations(self):
        monitor = SyntheticMonitor(alert_sink=lambda _payload: None)
        with self.assertRaises(SyntheticMonitorError):
            monitor.run_for(iterations=0)


class TestFromActionFiles(unittest.TestCase):

    def test_runner_called_per_file(self):
        called = []
        monitor = from_action_files(
            files=["a.json", "b.json"],
            runner=called.append,
        )
        monitor.tick_once()
        self.assertEqual(sorted(called), ["a.json", "b.json"])


if __name__ == "__main__":
    unittest.main()
