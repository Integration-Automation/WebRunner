import unittest

from je_web_runner.utils.pom_codegen import (
    PomCodegenError,
    discover_elements_from_html,
    render_pom_module,
)


class TestDiscoverElements(unittest.TestCase):

    def test_data_testid_priority(self):
        html = '<button data-testid="primary-cta" id="ignored-id">Go</button>'
        elements = discover_elements_from_html(html)
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].source, "data-testid")
        self.assertEqual(elements[0].strategy, "CSS_SELECTOR")
        self.assertIn('[data-testid="primary-cta"]', elements[0].value)

    def test_id_when_no_testid(self):
        html = '<input id="username"/>'
        elements = discover_elements_from_html(html)
        self.assertEqual(elements[0].strategy, "ID")
        self.assertEqual(elements[0].value, "username")

    def test_name_fallback(self):
        html = '<input name="email"/>'
        elements = discover_elements_from_html(html)
        self.assertEqual(elements[0].strategy, "NAME")
        self.assertEqual(elements[0].value, "email")

    def test_skip_unmarked_elements(self):
        html = '<div><span>raw</span><button data-testid="x">b</button></div>'
        elements = discover_elements_from_html(html)
        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0].source, "data-testid")

    def test_duplicate_names_disambiguated(self):
        html = (
            '<button data-testid="primary">A</button>'
            '<button data-testid="primary">B</button>'
        )
        elements = discover_elements_from_html(html)
        names = [e.name for e in elements]
        self.assertEqual(names, ["primary", "primary_2"])

    def test_invalid_input_raises(self):
        with self.assertRaises(PomCodegenError):
            discover_elements_from_html(123)  # type: ignore[arg-type]

    def test_python_keyword_suffixed(self):
        html = '<input id="class"/>'
        elements = discover_elements_from_html(html)
        self.assertTrue(elements[0].name.endswith("_"))


class TestRenderPomModule(unittest.TestCase):

    def test_renders_class_with_properties(self):
        html = (
            '<button data-testid="primary-cta">Go</button>'
            '<input id="username"/>'
        )
        elements = discover_elements_from_html(html)
        text = render_pom_module(elements, class_name="LoginPage")
        self.assertIn("class LoginPage:", text)
        self.assertIn("def primary_cta(self)", text)
        self.assertIn("def username(self)", text)
        self.assertIn('TestObject("username", "ID")', text)

    def test_invalid_class_name(self):
        with self.assertRaises(PomCodegenError):
            render_pom_module([], class_name="not a valid name")

    def test_empty_elements(self):
        text = render_pom_module([])
        self.assertIn("class WebRunnerPage:", text)
        self.assertIn("    pass", text)


if __name__ == "__main__":
    unittest.main()
