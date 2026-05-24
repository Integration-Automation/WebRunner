"""Unit tests for je_web_runner.utils.exploratory_ai."""
import unittest
from typing import List

from je_web_runner.utils.exploratory_ai.explorer import (
    ActionKind,
    BugSignal,
    ExploratoryAiError,
    Explorer,
    ExplorationReport,
    InteractiveElement,
    PageObservation,
    PlannedAction,
    RandomPlanner,
)


class StubObserver:
    def __init__(self, observations):
        self._observations = list(observations)

    def observe(self, step):
        if step < len(self._observations):
            return self._observations[step]
        # repeat last forever
        return self._observations[-1]


class FixedPlanner:
    def __init__(self, actions):
        self._actions = list(actions)
        self.calls = 0

    def plan(self, observation):
        if self.calls < len(self._actions):
            action = self._actions[self.calls]
        else:
            action = self._actions[-1]
        self.calls += 1
        return action


def _page(url, elements=None, errors=None):
    return PageObservation(
        url=url,
        title="t",
        elements=list(elements or []),
        console_errors=list(errors or []),
        step=0,
    )


class TestInteractiveElement(unittest.TestCase):

    def test_rejects_empty_selector(self):
        with self.assertRaises(ExploratoryAiError):
            InteractiveElement(selector="", tag="button")

    def test_rejects_empty_tag(self):
        with self.assertRaises(ExploratoryAiError):
            InteractiveElement(selector="#x", tag="")


class TestPlannedAction(unittest.TestCase):

    def test_click_requires_selector(self):
        with self.assertRaises(ExploratoryAiError):
            PlannedAction(kind=ActionKind.CLICK)

    def test_type_requires_value(self):
        with self.assertRaises(ExploratoryAiError):
            PlannedAction(kind=ActionKind.TYPE, selector="#x")

    def test_navigate_requires_value(self):
        with self.assertRaises(ExploratoryAiError):
            PlannedAction(kind=ActionKind.NAVIGATE)


class TestRandomPlanner(unittest.TestCase):

    def test_seeded_reproducible(self):
        page = _page("http://x", [
            InteractiveElement(selector="#a", tag="button"),
            InteractiveElement(selector="#b", tag="button"),
        ])
        a = RandomPlanner(seed=42).plan(page)
        b = RandomPlanner(seed=42).plan(page)
        self.assertEqual(a, b)

    def test_no_elements_returns_done(self):
        plan = RandomPlanner(seed=1).plan(_page("http://x", []))
        self.assertEqual(plan.kind, ActionKind.DONE)

    def test_type_bias_validated(self):
        with self.assertRaises(ExploratoryAiError):
            RandomPlanner(type_bias=2.0)

    def test_prefers_input_when_bias_high(self):
        page = _page("http://x", [
            InteractiveElement(selector="#btn", tag="button"),
            InteractiveElement(selector="#in", tag="input"),
        ])
        plan = RandomPlanner(seed=0, type_bias=1.0).plan(page)
        self.assertEqual(plan.kind, ActionKind.TYPE)
        self.assertEqual(plan.selector, "#in")

    def test_no_input_falls_back_to_click(self):
        page = _page("http://x", [
            InteractiveElement(selector="#btn", tag="button"),
        ])
        plan = RandomPlanner(seed=0, type_bias=1.0).plan(page)
        self.assertEqual(plan.kind, ActionKind.CLICK)


class TestExplorer(unittest.TestCase):

    def test_max_steps_must_be_positive(self):
        with self.assertRaises(ExploratoryAiError):
            Explorer(
                observer=StubObserver([_page("x")]),
                planner=FixedPlanner([PlannedAction(kind=ActionKind.DONE)]),
                executor=lambda a: None,
                max_steps=0,
            )

    def test_runs_until_done(self):
        observer = StubObserver([
            _page("http://1", [InteractiveElement(selector="#go", tag="button")]),
            _page("http://2", [InteractiveElement(selector="#go", tag="button")]),
        ])
        planner = FixedPlanner([
            PlannedAction(kind=ActionKind.CLICK, selector="#go"),
            PlannedAction(kind=ActionKind.DONE, rationale="finished"),
        ])
        executed: List[PlannedAction] = []
        explorer = Explorer(observer=observer, planner=planner,
                            executor=executed.append, max_steps=10)
        report = explorer.run()
        self.assertEqual(report.steps_taken, 1)
        self.assertEqual(len(executed), 1)
        self.assertIn("finished", report.stopped_reason)

    def test_collects_console_errors(self):
        observer = StubObserver([
            _page("http://1",
                  elements=[InteractiveElement(selector="#x", tag="button")],
                  errors=["TypeError: foo"]),
        ])
        planner = FixedPlanner([PlannedAction(kind=ActionKind.DONE)])
        explorer = Explorer(observer=observer, planner=planner,
                            executor=lambda a: None, max_steps=2)
        report = explorer.run()
        self.assertEqual(len([b for b in report.bugs if b.kind == "console_error"]), 1)

    def test_collects_network_errors(self):
        page = PageObservation(
            url="http://x", title="t",
            elements=[InteractiveElement(selector="#x", tag="button")],
            network_errors=[{"url": "/api/bad", "status": 500}],
        )
        planner = FixedPlanner([PlannedAction(kind=ActionKind.DONE)])
        explorer = Explorer(observer=StubObserver([page]), planner=planner,
                            executor=lambda a: None, max_steps=2)
        report = explorer.run()
        self.assertEqual(len([b for b in report.bugs if b.kind == "network_error"]), 1)

    def test_stuck_planner_stops(self):
        page = _page("http://1", [InteractiveElement(selector="#a", tag="button")])
        planner = FixedPlanner([PlannedAction(kind=ActionKind.CLICK, selector="#a")])
        explorer = Explorer(observer=StubObserver([page]), planner=planner,
                            executor=lambda a: None, max_steps=10, max_repeat_loops=2)
        report = explorer.run()
        self.assertIn("planner repeatedly", report.stopped_reason)
        self.assertTrue(any(b.kind == "planner_stuck" for b in report.bugs))

    def test_executor_error_recorded(self):
        page = _page("http://1", [InteractiveElement(selector="#a", tag="button")])
        planner = FixedPlanner([
            PlannedAction(kind=ActionKind.CLICK, selector="#a"),
            PlannedAction(kind=ActionKind.DONE),
        ])

        def boom(_):
            raise RuntimeError("click failed")

        explorer = Explorer(observer=StubObserver([page]), planner=planner,
                            executor=boom, max_steps=10)
        report = explorer.run()
        self.assertTrue(any(b.kind == "action_error" for b in report.bugs))

    def test_observer_failure_raises(self):
        class BadObserver:
            def observe(self, step):
                raise RuntimeError("driver dead")

        explorer = Explorer(observer=BadObserver(),
                            planner=FixedPlanner([PlannedAction(kind=ActionKind.DONE)]),
                            executor=lambda a: None, max_steps=2)
        with self.assertRaises(ExploratoryAiError):
            explorer.run()

    def test_planner_returning_wrong_type_raises(self):
        class BadPlanner:
            def plan(self, _obs):
                return "not a planned action"

        explorer = Explorer(
            observer=StubObserver([_page("http://x")]),
            planner=BadPlanner(),
            executor=lambda a: None,
            max_steps=2,
        )
        with self.assertRaises(ExploratoryAiError):
            explorer.run()

    def test_planner_exception_records_bug_and_stops(self):
        class BadPlanner:
            def plan(self, _obs):
                raise RuntimeError("llm timeout")

        explorer = Explorer(
            observer=StubObserver([_page("http://x")]),
            planner=BadPlanner(),
            executor=lambda a: None,
            max_steps=2,
        )
        report = explorer.run()
        self.assertTrue(any(b.kind == "planner_error" for b in report.bugs))

    def test_stop_on_bugs(self):
        observer = StubObserver([
            _page("http://x",
                  elements=[InteractiveElement(selector="#a", tag="button")],
                  errors=["err1", "err2", "err3"]),
        ])
        planner = FixedPlanner([PlannedAction(kind=ActionKind.CLICK, selector="#a")])
        explorer = Explorer(observer=observer, planner=planner,
                            executor=lambda a: None, max_steps=10, stop_on_bugs=2)
        report = explorer.run()
        self.assertIn("stop_on_bugs", report.stopped_reason)


class TestExplorationReport(unittest.TestCase):

    def test_has_bugs_default_false(self):
        self.assertFalse(ExplorationReport(steps_taken=0).has_bugs())
        report = ExplorationReport(
            steps_taken=1,
            bugs=[BugSignal(step=0, url="x", kind="console_error", detail="x")],
        )
        self.assertTrue(report.has_bugs())


if __name__ == "__main__":
    unittest.main()
