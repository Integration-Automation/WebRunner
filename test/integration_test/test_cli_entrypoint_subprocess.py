"""
Integration: the ``python -m je_web_runner`` CLI entry point.

Launches the package as a real subprocess so the ``__main__`` wiring
(import of cli_main.main + its error handling) is exercised end to end.
These paths need no browser.
"""
import subprocess  # nosec B404 — argv-only invocation, controlled args
import sys
import unittest


def _run(args):
    return subprocess.run(  # nosec B603 — argv list, no shell
        [sys.executable, "-m", "je_web_runner", *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


class TestCliEntryPoint(unittest.TestCase):

    def test_help_exits_zero_with_usage(self):
        result = _run(["--help"])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("usage:", result.stdout)

    def test_no_args_exits_nonzero_with_error(self):
        result = _run([])
        # __main__ catches the raised exception, prints its repr to stderr
        # and exits 1.
        self.assertEqual(result.returncode, 1)
        self.assertIn("WebRunnerExecuteException", result.stderr)


if __name__ == "__main__":
    unittest.main()
