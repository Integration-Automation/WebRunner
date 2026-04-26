"""Smoke-test the thematic façade so it stays in sync with the underlying modules."""
import importlib
import unittest


_FACADE_MODULES = [
    "je_web_runner.api.authoring",
    "je_web_runner.api.debugging",
    "je_web_runner.api.frontend",
    "je_web_runner.api.infra",
    "je_web_runner.api.mobile",
    "je_web_runner.api.networking",
    "je_web_runner.api.observability",
    "je_web_runner.api.quality",
    "je_web_runner.api.reliability",
    "je_web_runner.api.security",
    "je_web_runner.api.test_data",
]


class TestFacadeImports(unittest.TestCase):

    def test_top_level_api_re_exports_themes(self):
        package = importlib.import_module("je_web_runner.api")
        for theme in ("authoring", "debugging", "frontend", "infra", "mobile",
                      "networking", "observability", "quality", "reliability",
                      "security", "test_data"):
            self.assertTrue(
                hasattr(package, theme),
                msg=f"je_web_runner.api missing theme {theme!r}",
            )

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
        self.assertTrue(isinstance(observability.FailureBundle, type))

    def test_authoring_format_actions_callable(self):
        from je_web_runner.api import authoring
        self.assertTrue(callable(authoring.format_actions))

    def test_security_pii_redact_callable(self):
        from je_web_runner.api import security
        self.assertTrue(callable(security.redact_text))


if __name__ == "__main__":
    unittest.main()
