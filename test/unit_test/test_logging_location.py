"""Where ``WEBRunner.log`` goes: nothing at import, then the env var, the env dir, or the home default."""
import json
import os
import subprocess  # nosec B404 — this interpreter on a fixed snippet
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.logging import loggin_instance
from je_web_runner.utils.logging.loggin_instance import WebRunnerLoggingHandler, default_log_file

_REPO = Path(loggin_instance.__file__).resolve().parents[3]
_SNIPPET = """
import json, os, sys
from je_web_runner.utils.logging import loggin_instance as module
before = sorted(os.listdir("."))
existed = os.path.exists(module.file_handler.baseFilename)
module.web_runner_logger.warning("first record")
module.file_handler.flush()
print(json.dumps({"path": module.file_handler.baseFilename, "existed_after_import": existed,
                  "cwd_after_import": before}))
"""


def _run(cwd: Path, env: dict) -> dict:
    environment = {key: value for key, value in os.environ.items()
                   if key not in ("WEBRUNNER_LOG_PATH", "WEBRUNNER_LOG_DIR")}
    environment.update(env, PYTHONPATH=str(_REPO))
    result = subprocess.run([sys.executable, "-c", _SNIPPET], cwd=cwd, env=environment,  # nosec B603
                            capture_output=True, text=True, encoding="utf-8", timeout=120, check=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


class TestLogLocation(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cwd = self.root / "cwd"
        self.cwd.mkdir()

    def test_import_writes_nothing_and_the_first_record_lands_in_the_configured_file(self):
        target = self.root / "logs" / "batch.log"
        outcome = _run(self.cwd, {"WEBRUNNER_LOG_PATH": str(target)})
        self.assertEqual(Path(outcome["path"]), target)
        self.assertFalse(outcome["existed_after_import"])
        self.assertEqual(outcome["cwd_after_import"], [])
        line = target.read_text(encoding="utf-8").splitlines()[-1]
        self.assertIn("| WEBRunner | WARNING | first record", line)
        self.assertRegex(line, r"\| \d+ \| WEBRunner")  # the process id
        self.assertEqual(list(self.cwd.iterdir()), [])

    def test_the_file_is_appended_not_overwritten(self):
        target = self.root / "shared.log"
        _run(self.cwd, {"WEBRUNNER_LOG_PATH": str(target)})
        _run(self.cwd, {"WEBRUNNER_LOG_PATH": str(target)})
        self.assertEqual(target.read_text(encoding="utf-8").count("first record"), 2)

    def test_the_directory_variable_and_the_home_default(self):
        outcome = _run(self.cwd, {"WEBRUNNER_LOG_DIR": str(self.root / "dir")})
        self.assertEqual(Path(outcome["path"]), self.root / "dir" / "WEBRunner.log")
        home = self.root / "home"
        outcome = _run(self.cwd, {"USERPROFILE": str(home), "HOME": str(home)})
        self.assertEqual(Path(outcome["path"]), home / ".je_web_runner" / "logs" / "WEBRunner.log")
        self.assertEqual(list(self.cwd.iterdir()), [])

    def test_the_path_variable_wins_over_the_directory(self):
        with patch.dict(os.environ, {"WEBRUNNER_LOG_PATH": "a.log", "WEBRUNNER_LOG_DIR": "dir"}):
            self.assertEqual(default_log_file(), Path("a.log"))

    def test_an_unopenable_file_turns_file_logging_off_with_one_warning(self):
        handler = WebRunnerLoggingHandler(filename=str(self.root), delay=True)  # a directory, not a file
        self.addCleanup(handler.close)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            handler.emit(loggin_instance.web_runner_logger.makeRecord(
                "WEBRunner", 30, __file__, 1, "dropped", (), None))
        self.assertTrue(any(issubclass(w.category, RuntimeWarning) for w in caught))


if __name__ == "__main__":
    unittest.main()
