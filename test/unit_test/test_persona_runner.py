"""Unit tests for je_web_runner.utils.persona_runner."""
import unittest

from je_web_runner.utils.persona_runner.runner import (
    MatrixSummary,
    Persona,
    PersonaCaseResult,
    PersonaRunner,
    PersonaRunnerError,
    summarise,
    summary_markdown,
)


def _make_personas(*names):
    return [Persona(name=n) for n in names]


class TestPersona(unittest.TestCase):

    def test_rejects_empty_name(self):
        with self.assertRaises(PersonaRunnerError):
            Persona(name="")


class TestPersonaRunner(unittest.TestCase):

    def test_rejects_no_personas(self):
        with self.assertRaises(PersonaRunnerError):
            PersonaRunner(personas=[], action_files=["a"], case_runner=lambda p, f: None)

    def test_rejects_no_files(self):
        with self.assertRaises(PersonaRunnerError):
            PersonaRunner(personas=_make_personas("a"), action_files=[],
                          case_runner=lambda p, f: None)

    def test_rejects_duplicate_personas(self):
        with self.assertRaises(PersonaRunnerError):
            PersonaRunner(personas=_make_personas("a", "a"), action_files=["x"],
                          case_runner=lambda p, f: None)

    def test_rejects_duplicate_files(self):
        with self.assertRaises(PersonaRunnerError):
            PersonaRunner(personas=_make_personas("a"), action_files=["x", "x"],
                          case_runner=lambda p, f: None)

    def test_runs_full_matrix(self):
        called = []
        runner = PersonaRunner(
            personas=_make_personas("admin", "guest"),
            action_files=["a.json", "b.json"],
            case_runner=lambda p, f: called.append((p.name, f)),
        )
        results = runner.run()
        self.assertEqual(len(results), 4)
        self.assertTrue(all(r.passed for r in results))
        self.assertEqual(len(called), 4)

    def test_records_failures(self):
        def runner(persona, file):
            if persona.name == "guest":
                raise AssertionError("guest cannot")
        results = PersonaRunner(
            personas=_make_personas("admin", "guest"),
            action_files=["x.json"],
            case_runner=runner,
        ).run()
        self.assertEqual([r.passed for r in results], [True, False])
        self.assertIn("guest cannot", results[1].error or "")

    def test_stop_on_first_failure(self):
        called = []

        def runner(persona, file):
            called.append((persona.name, file))
            if persona.name == "admin":
                raise RuntimeError("nope")
        results = PersonaRunner(
            personas=_make_personas("admin", "guest"),
            action_files=["a", "b"],
            case_runner=runner,
            stop_on_first_failure=True,
        ).run()
        self.assertEqual(len(results), 1)
        self.assertEqual(len(called), 1)


class TestSummarise(unittest.TestCase):

    def test_counts(self):
        results = [
            PersonaCaseResult(persona="admin", action_file="a", passed=True),
            PersonaCaseResult(persona="admin", action_file="b", passed=False),
            PersonaCaseResult(persona="guest", action_file="a", passed=True),
            PersonaCaseResult(persona="guest", action_file="b", passed=True),
        ]
        s = summarise(results)
        self.assertEqual(s.total, 4)
        self.assertEqual(s.passed, 3)
        self.assertEqual(s.failed, 1)
        self.assertEqual(s.by_persona["admin"], {"passed": 1, "failed": 1})

    def test_persona_only_failure_detected(self):
        results = [
            PersonaCaseResult(persona="admin", action_file="dashboard", passed=False),
            PersonaCaseResult(persona="guest", action_file="dashboard", passed=True),
        ]
        s = summarise(results)
        self.assertIn("admin", s.persona_only_failures)

    def test_file_only_failure_detected(self):
        results = [
            PersonaCaseResult(persona="admin", action_file="broken", passed=False),
            PersonaCaseResult(persona="guest", action_file="broken", passed=False),
            PersonaCaseResult(persona="admin", action_file="ok", passed=True),
            PersonaCaseResult(persona="guest", action_file="ok", passed=True),
        ]
        s = summarise(results)
        self.assertIn("broken", s.file_only_failures)

    def test_rejects_bad_input(self):
        with self.assertRaises(PersonaRunnerError):
            summarise(["string"])  # type: ignore[list-item]


class TestSummaryMarkdown(unittest.TestCase):

    def test_empty(self):
        md = summary_markdown(MatrixSummary(total=0, passed=0, failed=0))
        self.assertIn("No persona matrix", md)

    def test_with_failures(self):
        s = MatrixSummary(
            total=4, passed=3, failed=1,
            by_persona={"admin": {"passed": 1, "failed": 1},
                        "guest": {"passed": 2, "failed": 0}},
            persona_only_failures=["admin"],
        )
        md = summary_markdown(s)
        self.assertIn("Persona matrix: 3/4", md)
        self.assertIn("admin", md)
        self.assertIn("Persona-specific regressions", md)


if __name__ == "__main__":
    unittest.main()
