import unittest

from je_web_runner.utils.action_templates import (
    ActionTemplate,
    ActionTemplateError,
    available_templates,
    get_template,
    register_template,
    render_template,
)


class TestRenderTemplate(unittest.TestCase):

    def test_login_basic_renders(self):
        actions = render_template("login_basic", {
            "username_locator": "#user",
            "password_locator": "#pass",
            "submit_locator": "#go",
            "username": "alice",
            "password": "wonderland",
        })
        # The fill step should have substituted "alice"
        flat = repr(actions)
        self.assertIn("alice", flat)
        self.assertIn("wonderland", flat)

    def test_switch_locale_string_substitution(self):
        actions = render_template("switch_locale", {
            "base_url": "https://example.com/",
            "locale": "ja-JP",
        })
        self.assertEqual(actions[0][1]["url"], "https://example.com/?lang=ja-JP")

    def test_missing_parameter_raises(self):
        with self.assertRaises(ActionTemplateError):
            render_template("switch_locale", {"base_url": "x"})

    def test_unknown_template_raises(self):
        with self.assertRaises(ActionTemplateError):
            render_template("ghost")

    def test_no_params_template(self):
        actions = render_template("close_modal")
        self.assertEqual(len(actions), 2)


class TestRegisterTemplate(unittest.TestCase):

    def test_register_and_use(self):
        register_template(ActionTemplate(
            name="hello",
            parameters=("who",),
            actions=[["WR_say", {"who": "{{who}}"}]],
        ))
        actions = render_template("hello", {"who": "world"})
        self.assertEqual(actions[0][1]["who"], "world")
        self.assertIn("hello", available_templates())

    def test_register_rejects_non_template(self):
        with self.assertRaises(ActionTemplateError):
            register_template({"name": "bad"})  # type: ignore[arg-type]


class TestGetTemplate(unittest.TestCase):

    def test_get_existing(self):
        template = get_template("login_basic")
        self.assertEqual(template.name, "login_basic")

    def test_get_missing(self):
        with self.assertRaises(ActionTemplateError):
            get_template("not-there")


if __name__ == "__main__":
    unittest.main()
