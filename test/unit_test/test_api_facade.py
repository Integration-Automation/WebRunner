"""Smoke-test the thematic façade so it stays in sync with the underlying modules."""
import importlib
import importlib.util
import unittest
from pathlib import Path


_API_DIR = Path(__file__).resolve().parents[2] / "je_web_runner" / "api"
_THEMES = sorted(path.stem for path in _API_DIR.glob("*.py") if path.name != "__init__.py")
_FACADE_MODULES = [f"je_web_runner.api.{theme}" for theme in _THEMES]
_GENERATOR = Path(__file__).resolve().parents[2] / "scripts" / "gen_utils_index.py"


def _index_generator():
    spec = importlib.util.spec_from_file_location("gen_utils_index", _GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFacadeImports(unittest.TestCase):

    def test_top_level_api_re_exports_themes(self):
        package = importlib.import_module("je_web_runner.api")
        self.assertEqual(sorted(package.__all__), _THEMES)
        for theme in _THEMES:
            self.assertTrue(
                hasattr(package, theme),
                msg=f"je_web_runner.api missing theme {theme!r}",
            )

    def test_every_utils_subpackage_is_core_or_in_a_theme(self):
        # A new subpackage must be re-exported by one theme (or be part of the core engine).
        generator = _index_generator()
        placed = set(generator.CORE).union(*(members for _heading, members in generator.facade_themes().values()))
        self.assertEqual(sorted(set(generator.subpackages()) - placed), [])

    def test_each_theme_has_all(self):
        for module_name in _FACADE_MODULES:
            module = importlib.import_module(module_name)
            self.assertIsInstance(module.__all__, list,
                                  msg=f"{module_name} missing __all__")
            self.assertTrue(module.__all__,
                            msg=f"{module_name}.__all__ is empty")

    def test_all_names_are_resolvable(self):
        # Each name in __all__ must be a real attribute on the façade module.
        for module_name in _FACADE_MODULES:
            module = importlib.import_module(module_name)
            for name in module.__all__:
                self.assertTrue(
                    hasattr(module, name),
                    msg=f"{module_name}.{name} not defined",
                )

    def test_no_duplicate_exports_within_theme(self):
        # A theme accidentally listing the same name twice would shadow itself
        # silently, so guard against it.
        for module_name in _FACADE_MODULES:
            module = importlib.import_module(module_name)
            self.assertEqual(
                len(module.__all__),
                len(set(module.__all__)),
                msg=f"{module_name} has duplicate entries in __all__",
            )


class TestFacadeSpotChecks(unittest.TestCase):

    def test_reliability_run_with_retry_callable(self):
        from je_web_runner.api import reliability
        self.assertTrue(callable(reliability.run_with_retry))

    def test_quality_diff_violations_callable(self):
        from je_web_runner.api import quality
        self.assertTrue(callable(quality.diff_violations))

    def test_observability_failure_bundle_class(self):
        from je_web_runner.api import observability
        self.assertIsInstance(observability.FailureBundle, type)

    def test_authoring_format_actions_callable(self):
        from je_web_runner.api import authoring
        self.assertTrue(callable(authoring.format_actions))

    def test_new_themes_spot_check(self):
        from je_web_runner.api import audit, performance, platform
        self.assertTrue(callable(performance.assert_web_vitals))
        self.assertTrue(callable(platform.ac_run))
        self.assertTrue(callable(audit.cors_matrix_classify))

    def test_security_pii_redact_callable(self):
        from je_web_runner.api import security
        self.assertTrue(callable(security.redact_text))


if __name__ == "__main__":
    unittest.main()
