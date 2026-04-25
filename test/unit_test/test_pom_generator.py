import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.pom_generator.pom_generator import (
    POMGeneratorError,
    extract_elements_from_html,
    generate_pom_class,
    generate_pom_from_html,
    generate_pom_from_url,
    write_pom_to_file,
)


_LOGIN_HTML = """
<html><body>
  <input id="username" name="user" type="text" placeholder="Username" />
  <input id="password" name="pass" type="password" />
  <button id="submit-btn">Sign in</button>
  <a href="/forgot" class="link-secondary">Forgot password?</a>
  <select name="locale"><option>en</option></select>
</body></html>
"""


class TestExtraction(unittest.TestCase):

    def test_extracts_inputs_button_link_select(self):
        elements = extract_elements_from_html(_LOGIN_HTML)
        tags = [element["tag"] for element in elements]
        self.assertIn("input", tags)
        self.assertIn("button", tags)
        self.assertIn("a", tags)
        self.assertIn("select", tags)

    def test_button_text_is_collected(self):
        elements = extract_elements_from_html(_LOGIN_HTML)
        button = next(element for element in elements if element["tag"] == "button")
        self.assertEqual(button["text"], "Sign in")


class TestGenerate(unittest.TestCase):

    def test_generated_class_has_constants_and_methods(self):
        source = generate_pom_from_html(_LOGIN_HTML, "LoginPage")
        self.assertIn("class LoginPage", source)
        self.assertIn("USERNAME", source)
        self.assertIn("PASSWORD", source)
        self.assertIn("def input_to_username", source)
        self.assertIn("def input_to_password", source)
        self.assertIn("def click_submit_btn", source)

    def test_generate_pom_class_handles_no_elements(self):
        source = generate_pom_class("EmptyPage", [])
        self.assertIn("# no interactive elements detected", source)
        self.assertIn("# no methods generated", source)

    def test_method_names_disambiguate(self):
        elements = [
            {"tag": "button", "id": "go", "name": None, "type": None, "class": None,
             "href": None, "placeholder": None, "text": "Go"},
            {"tag": "button", "id": "go", "name": None, "type": None, "class": None,
             "href": None, "placeholder": None, "text": "Go"},
        ]
        source = generate_pom_class("Page", elements)
        # Same id used twice → constants and methods should be disambiguated.
        self.assertIn("GO ", source)
        self.assertIn("GO_2", source)
        self.assertIn("def click_go", source)
        self.assertIn("def click_go_2", source)


class TestUrlFetch(unittest.TestCase):

    def test_url_must_be_http(self):
        with self.assertRaises(POMGeneratorError):
            generate_pom_from_url("ftp://example.com", "X")

    def test_fetches_and_generates(self):
        response = MagicMock()
        response.text = _LOGIN_HTML
        response.raise_for_status = MagicMock()
        with patch("je_web_runner.utils.pom_generator.pom_generator.requests.get",
                   return_value=response) as get_mock:
            source = generate_pom_from_url("https://example.com/login", "LoginPage")
            get_mock.assert_called_once()
            self.assertIn("class LoginPage", source)


class TestWriteToFile(unittest.TestCase):

    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "nested", "out.py")
            path = write_pom_to_file("class X: pass\n", target)
            self.assertEqual(path, target)
            self.assertTrue(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()
