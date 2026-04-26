import unittest

from je_web_runner.utils.sel_to_pw import (
    SelToPwError,
    translate_action_list,
    translate_python_source,
)
from je_web_runner.utils.sel_to_pw.translator import (
    supported_action_commands,
    supported_python_patterns,
)


class TestTranslatePython(unittest.TestCase):

    def test_translates_id_locator(self):
        source = "el = driver.find_element(By.ID, 'submit')"
        results = translate_python_source(source)
        self.assertEqual(len(results), 1)
        self.assertIn("page.locator('#submit')", results[0].translated)

    def test_translates_get_to_goto(self):
        source = "driver.get('https://example.com')"
        results = translate_python_source(source)
        self.assertIn("page.goto('https://example.com')", results[0].translated)

    def test_translates_send_keys_to_fill(self):
        source = "el.send_keys('hello')"
        results = translate_python_source(source)
        self.assertIn(".fill('hello')", results[0].translated)

    def test_drops_implicit_wait(self):
        source = "driver.implicitly_wait(5)"
        results = translate_python_source(source)
        self.assertIn("auto-waits", results[0].translated)

    def test_text_property_to_inner_text(self):
        source = "value = el.text"
        results = translate_python_source(source)
        self.assertIn(".inner_text()", results[0].translated)

    def test_unchanged_line_skipped(self):
        source = "x = 1"
        self.assertEqual(translate_python_source(source), [])

    def test_non_string_raises(self):
        with self.assertRaises(SelToPwError):
            translate_python_source(b"bytes")  # type: ignore[arg-type]

    def test_supported_patterns_list_non_empty(self):
        self.assertGreater(len(supported_python_patterns()), 5)


class TestTranslateActionList(unittest.TestCase):

    def test_known_command_rewritten(self):
        actions = [["WR_to_url", {"url": "https://x.com"}]]
        result = translate_action_list(actions)
        self.assertEqual(result[0][0], "WR_pw_to_url")

    def test_drops_implicit_wait(self):
        actions = [["WR_implicitly_wait", {"time_to_wait": 5}],
                   ["WR_quit_all"]]
        result = translate_action_list(actions)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "WR_pw_close_context")

    def test_unknown_command_passes_through(self):
        actions = [["WR_custom_action", {"x": 1}]]
        result = translate_action_list(actions)
        self.assertEqual(result, [["WR_custom_action", {"x": 1}]])

    def test_invalid_input_raises(self):
        with self.assertRaises(SelToPwError):
            translate_action_list("not a list")  # type: ignore[arg-type]

    def test_supported_commands_includes_to_url(self):
        self.assertIn("WR_to_url", supported_action_commands())


if __name__ == "__main__":
    unittest.main()
