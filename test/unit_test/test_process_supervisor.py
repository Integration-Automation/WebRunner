import os
import time
import unittest

from je_web_runner.utils.process_supervisor import (
    KNOWN_DRIVER_NAMES,
    OrphanFinding,
    ProcessSupervisor,
    ProcessSupervisorError,
)
from je_web_runner.utils.process_supervisor.supervisor import with_watchdog


class TestProcessSupervisor(unittest.TestCase):

    def test_list_filters_by_name(self):
        all_findings = [
            OrphanFinding(pid=1, name="chromedriver"),
            OrphanFinding(pid=2, name="python"),
            OrphanFinding(pid=3, name="GECKODRIVER"),
        ]
        supervisor = ProcessSupervisor(
            lister=lambda: all_findings,
            killer=lambda _pid: True,
        )
        orphans = supervisor.list_orphans()
        pids = sorted(o.pid for o in orphans)
        self.assertEqual(pids, [1, 3])

    def test_kill_orphans_skips_self_and_protected(self):
        all_findings = [
            OrphanFinding(pid=1, name="chromedriver"),
            OrphanFinding(pid=2, name="geckodriver"),
            OrphanFinding(pid=os.getpid(), name="chromedriver"),
        ]
        killed = []
        supervisor = ProcessSupervisor(
            lister=lambda: all_findings,
            killer=lambda pid: (killed.append(pid), True)[1],
        )
        result = supervisor.kill_orphans(protected_pids=[2])
        self.assertEqual(killed, [1])
        self.assertEqual(result, {1: True})

    def test_kill_failure_recorded(self):
        all_findings = [OrphanFinding(pid=1, name="chromedriver")]
        supervisor = ProcessSupervisor(
            lister=lambda: all_findings,
            killer=lambda _pid: False,
        )
        result = supervisor.kill_orphans()
        self.assertEqual(result, {1: False})

    def test_lister_must_return_list(self):
        supervisor = ProcessSupervisor(
            lister=lambda: "not-a-list",  # type: ignore[return-value]
            killer=lambda _pid: True,
        )
        with self.assertRaises(ProcessSupervisorError):
            supervisor.list_orphans()


class TestWithWatchdog(unittest.TestCase):

    def test_returns_value_under_deadline(self):
        result = with_watchdog(lambda: 42, timeout_seconds=0.5)
        self.assertEqual(result, 42)

    def test_propagates_errors(self):
        def boom():
            raise RuntimeError("nope")
        with self.assertRaises(RuntimeError):
            with_watchdog(boom, timeout_seconds=0.5)

    def test_fires_when_blocked(self):
        def blocker():
            time.sleep(0.5)

        with self.assertRaises(ProcessSupervisorError):
            with_watchdog(blocker, timeout_seconds=0.05)

    def test_invalid_timeout(self):
        with self.assertRaises(ProcessSupervisorError):
            with_watchdog(lambda: None, timeout_seconds=0)


class TestKnownDriverNames(unittest.TestCase):

    def test_includes_common_drivers(self):
        self.assertIn("chromedriver", KNOWN_DRIVER_NAMES)
        self.assertIn("geckodriver", KNOWN_DRIVER_NAMES)


if __name__ == "__main__":
    unittest.main()
