"""Unit tests for je_web_runner.utils.story_to_actions."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.story_to_actions.generator import (
    ALLOWED_ACTIONS,
    FigmaHint,
    StoryPrompt,
    StoryToActionsError,
    build_prompt_text,
    generate_actions,
    validate_actions,
    write_actions_json,
)


class StubClient:
    def __init__(self, response):
        self.response = response
        self.last_prompt = None

    def generate(self, prompt_text):
        self.last_prompt = prompt_text
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class TestStoryPrompt(unittest.TestCase):

    def test_rejects_empty_story(self):
        with self.assertRaises(StoryToActionsError):
            StoryPrompt(story="")

    def test_rejects_whitespace_story(self):
        with self.assertRaises(StoryToActionsError):
            StoryPrompt(story="   \n  ")


class TestBuildPrompt(unittest.TestCase):

    def test_includes_story_and_url(self):
        prompt = StoryPrompt(story="Add to cart", start_url="https://shop/")
        text = build_prompt_text(prompt)
        self.assertIn("Add to cart", text)
        self.assertIn("https://shop/", text)

    def test_includes_figma_hints(self):
        prompt = StoryPrompt(
            story="Click checkout",
            figma_hints=[FigmaHint(name="checkout_btn", type="button",
                                   selector_hint="[data-test=checkout]",
                                   text="Checkout")],
        )
        text = build_prompt_text(prompt)
        self.assertIn("checkout_btn", text)
        self.assertIn("[data-test=checkout]", text)

    def test_includes_style_notes(self):
        text = build_prompt_text(StoryPrompt(story="x", style_notes=["prefer id locators"]))
        self.assertIn("prefer id locators", text)


class TestValidate(unittest.TestCase):

    def test_empty_rejected(self):
        with self.assertRaises(StoryToActionsError):
            validate_actions([])

    def test_non_list_rejected(self):
        with self.assertRaises(StoryToActionsError):
            validate_actions({"WR_to_url": ["x"]})  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test

    def test_unknown_action_name(self):
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_fly_to_moon": []}])

    def test_multi_key_action_rejected(self):
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_to_url": ["x"], "extra": []}])

    def test_args_must_be_list(self):
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_to_url": "x"}])

    def test_to_url_needs_string(self):
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_to_url": []}])
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_to_url": [""]}])

    def test_implicitly_wait_needs_number(self):
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_implicitly_wait": ["soon"]}])
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_implicitly_wait": [-1]}])

    def test_click_needs_locator(self):
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_click_element": ["#x"]}])
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_click_element": ["unknown_by", "#x"]}])

    def test_input_needs_text(self):
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_input_to_element": ["id", "name"]}])

    def test_assert_text_needs_expected(self):
        with self.assertRaises(StoryToActionsError):
            validate_actions([{"WR_assert_element_text": ["id", "x"]}])

    def test_valid_passes(self):
        validate_actions([
            {"WR_to_url": ["https://x"]},
            {"WR_click_element": ["id", "submit"]},
            {"WR_input_to_element": ["css selector", "#name", "alice"]},
            {"WR_assert_element_text": ["id", "status", "OK"]},
            {"WR_assert_element_visible": ["id", "ok"]},
            {"WR_implicitly_wait": [1.5]},
            {"WR_comment": ["done"]},
        ])

    def test_allowed_actions_visible(self):
        self.assertIn("WR_to_url", ALLOWED_ACTIONS)


class TestGenerateActions(unittest.TestCase):

    def test_happy_path(self):
        client = StubClient(json.dumps([
            {"WR_to_url": ["https://x"]},
            {"WR_click_element": ["id", "submit"]},
        ]))
        actions = generate_actions(StoryPrompt(story="open the page"), client)
        self.assertEqual(len(actions), 2)
        self.assertIsNotNone(client.last_prompt)
        self.assertIn("open the page", client.last_prompt)

    def test_strips_markdown_fence(self):
        client = StubClient('```json\n[{"WR_to_url": ["https://x"]}]\n```')
        actions = generate_actions(StoryPrompt(story="x"), client)
        self.assertEqual(actions, [{"WR_to_url": ["https://x"]}])

    def test_prepends_start_url_when_missing(self):
        client = StubClient(json.dumps([{"WR_click_element": ["id", "go"]}]))
        actions = generate_actions(
            StoryPrompt(story="x", start_url="https://shop/"),
            client,
        )
        self.assertEqual(actions[0], {"WR_to_url": ["https://shop/"]})
        self.assertEqual(len(actions), 2)

    def test_does_not_duplicate_start_url(self):
        client = StubClient(json.dumps([
            {"WR_to_url": ["https://shop/"]},
            {"WR_click_element": ["id", "go"]},
        ]))
        actions = generate_actions(
            StoryPrompt(story="x", start_url="https://shop/"),
            client,
        )
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0], {"WR_to_url": ["https://shop/"]})

    def test_invalid_action_propagates(self):
        client = StubClient(json.dumps([{"WR_fake": []}]))
        with self.assertRaises(StoryToActionsError):
            generate_actions(StoryPrompt(story="x"), client)

    def test_client_error_wrapped(self):
        client = StubClient(RuntimeError("network down"))
        with self.assertRaises(StoryToActionsError):
            generate_actions(StoryPrompt(story="x"), client)

    def test_non_string_response_rejected(self):
        class WeirdClient:
            def generate(self, _p):
                return 42
        with self.assertRaises(StoryToActionsError):
            generate_actions(StoryPrompt(story="x"), WeirdClient())

    def test_bad_json_response(self):
        client = StubClient("not json at all")
        with self.assertRaises(StoryToActionsError):
            generate_actions(StoryPrompt(story="x"), client)

    def test_non_list_response(self):
        client = StubClient(json.dumps({"WR_to_url": ["x"]}))
        with self.assertRaises(StoryToActionsError):
            generate_actions(StoryPrompt(story="x"), client)


class TestWriteActions(unittest.TestCase):

    def test_write(self):
        actions = [{"WR_to_url": ["https://x"]}]
        with tempfile.TemporaryDirectory() as tmp:
            out = write_actions_json(actions, Path(tmp) / "actions.json")
            self.assertEqual(
                json.loads(out.read_text(encoding="utf-8")),
                actions,
            )

    def test_write_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StoryToActionsError):
                write_actions_json([{"WR_fake": []}], Path(tmp) / "actions.json")


if __name__ == "__main__":
    unittest.main()
