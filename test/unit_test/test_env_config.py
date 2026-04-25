import os
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.env_config.env_loader import (
    EnvConfigError,
    expand_in_action,
    get_env,
    load_env,
)


class TestLoadEnv(unittest.TestCase):

    def setUp(self):
        self._original_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._original_env)

    def _write_env(self, dir_path: str, name: str, content: str) -> str:
        target = Path(dir_path) / name
        target.write_text(content, encoding="utf-8")
        return str(target)

    def test_load_default_dot_env(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_env(tmpdir, ".env", "BASE_URL=https://default.example\n")
            load_env(env_dir=tmpdir)
            self.assertEqual(os.environ["BASE_URL"], "https://default.example")

    def test_load_named_env(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_env(tmpdir, ".env.staging", "BASE_URL=https://staging.example\n")
            load_env("staging", env_dir=tmpdir)
            self.assertEqual(os.environ["BASE_URL"], "https://staging.example")

    def test_missing_env_file_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(EnvConfigError):
                load_env("nope", env_dir=tmpdir)

    def test_get_env_returns_default(self):
        os.environ.pop("ABSENT_KEY_FOR_TEST", None)
        self.assertEqual(get_env("ABSENT_KEY_FOR_TEST", "fallback"), "fallback")

    def test_override_flag_replaces_existing(self):
        os.environ["BASE_URL"] = "old"
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_env(tmpdir, ".env", "BASE_URL=new\n")
            load_env(env_dir=tmpdir, override=True)
            self.assertEqual(os.environ["BASE_URL"], "new")


class TestExpandInAction(unittest.TestCase):

    def setUp(self):
        os.environ["TEST_BASE_URL"] = "https://test.example"
        os.environ["TEST_USER"] = "alice"

    def tearDown(self):
        os.environ.pop("TEST_BASE_URL", None)
        os.environ.pop("TEST_USER", None)

    def test_expand_string(self):
        self.assertEqual(expand_in_action("${ENV.TEST_BASE_URL}/login"), "https://test.example/login")

    def test_expand_dict_and_list(self):
        action = [
            ["WR_to_url", {"url": "${ENV.TEST_BASE_URL}/page"}],
            ["WR_input_to_element", {"input_value": "${ENV.TEST_USER}"}],
        ]
        result = expand_in_action(action)
        self.assertEqual(result[0][1]["url"], "https://test.example/page")
        self.assertEqual(result[1][1]["input_value"], "alice")

    def test_unresolved_placeholder_raises(self):
        with self.assertRaises(EnvConfigError):
            expand_in_action("${ENV.DEFINITELY_NOT_SET_QQQ}")

    def test_non_string_values_pass_through(self):
        self.assertEqual(expand_in_action(42), 42)
        self.assertIsNone(expand_in_action(None))


if __name__ == "__main__":
    unittest.main()
