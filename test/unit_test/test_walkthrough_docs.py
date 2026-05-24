"""Unit tests for je_web_runner.utils.walkthrough_docs."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.ai_assist.llm_assist import set_llm_callable
from je_web_runner.utils.walkthrough_docs.generator import (
    Walkthrough,
    WalkthroughError,
    WalkthroughStep,
    build_walkthrough,
    collect_steps,
    narrate_steps,
    render_confluence,
    render_markdown,
    save_walkthrough,
)


SAMPLE_ACTIONS = [
    ["WR_init", {}],                                  # noise — filtered
    ["WR_to_url", {"url": "https://shop.example/cart"}],
    ["WR_save_test_object", {"object_type": "ID",     # noise
                              "test_object_name": "checkout"}],
    ["WR_element_click", {"test_object_name": "checkout"}],
    ["WR_set_timeout", {"timeout": 5}],               # noise
    ["WR_element_input", {"test_object_name": "promo", "text": "SAVE10"}],
    ["WR_element_assert_text", {"test_object_name": "total",
                                 "expected": "$90"}],
]


class TestCollectSteps(unittest.TestCase):

    def test_filters_noise(self):
        steps = collect_steps(SAMPLE_ACTIONS)
        commands = [s.action_command for s in steps]
        self.assertIn("WR_to_url", commands)
        self.assertIn("WR_element_click", commands)
        self.assertNotIn("WR_init", commands)
        self.assertNotIn("WR_save_test_object", commands)
        self.assertNotIn("WR_set_timeout", commands)

    def test_skip_noise_disabled(self):
        steps = collect_steps(SAMPLE_ACTIONS, skip_noise=False)
        commands = [s.action_command for s in steps]
        self.assertIn("WR_init", commands)

    def test_non_list_raises(self):
        with self.assertRaises(WalkthroughError):
            collect_steps("not a list")  # type: ignore[arg-type]

    def test_screenshot_bytes_attached(self):
        png = b"\x89PNG\r\n\x1a\n" + b"x" * 20
        steps = collect_steps(SAMPLE_ACTIONS, screenshots={3: png})
        click_step = next(s for s in steps if s.action_command == "WR_element_click")
        self.assertIsNotNone(click_step.screenshot_b64)

    def test_screenshot_file_attached(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "shot.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 4)
            steps = collect_steps(SAMPLE_ACTIONS, screenshots={3: path})
            click_step = next(s for s in steps if s.action_command == "WR_element_click")
            self.assertEqual(click_step.screenshot_path, str(path))
            self.assertIsNotNone(click_step.screenshot_b64)
            self.assertEqual(click_step.screenshot_mime, "image/png")

    def test_missing_screenshot_file_is_warned_not_raised(self):
        steps = collect_steps(SAMPLE_ACTIONS, screenshots={3: "/no/such.png"})
        click_step = next(s for s in steps if s.action_command == "WR_element_click")
        self.assertIsNone(click_step.screenshot_path)


class TestNarrate(unittest.TestCase):

    def tearDown(self):
        set_llm_callable(None)

    def test_assigns_narrations_in_order(self):
        wt = Walkthrough(
            title="Checkout",
            steps=[
                WalkthroughStep(index=0, action_command="WR_to_url"),
                WalkthroughStep(index=1, action_command="WR_element_click"),
            ],
        )
        payload = json.dumps({
            "steps": [
                "Open the cart page.",
                "Click the checkout button.",
            ]
        })
        set_llm_callable(lambda _p: payload)
        narrate_steps(wt)
        self.assertEqual(wt.steps[0].narration, "Open the cart page.")
        self.assertEqual(wt.steps[1].narration, "Click the checkout button.")

    def test_no_steps_returns_early(self):
        wt = Walkthrough(title="empty")
        # should not call LLM at all — no callable registered, no error
        narrate_steps(wt)
        self.assertEqual(wt.steps, [])

    def test_missing_steps_key_raises(self):
        wt = Walkthrough(title="x", steps=[
            WalkthroughStep(index=0, action_command="WR_x"),
        ])
        set_llm_callable(lambda _p: "{}")
        with self.assertRaises(WalkthroughError):
            narrate_steps(wt)

    def test_no_callable_raises_when_steps_exist(self):
        wt = Walkthrough(title="x", steps=[
            WalkthroughStep(index=0, action_command="WR_x"),
        ])
        set_llm_callable(None)
        with self.assertRaises(WalkthroughError):
            narrate_steps(wt)


class TestRendering(unittest.TestCase):

    def _wt(self, with_image=False):
        steps = [
            WalkthroughStep(index=0, action_command="WR_to_url",
                            kwargs={"url": "https://x"}, narration="Visit the site."),
            WalkthroughStep(index=1, action_command="WR_element_click",
                            kwargs={"test_object_name": "btn"},
                            narration="Click the button."),
        ]
        if with_image:
            steps[1].screenshot_b64 = "deadbeef"
            # Use a path under tempfile.gettempdir() rather than a hard-coded
            # /tmp/ literal so SonarCloud's S5443 (insecure temp file) is happy
            # and the test still passes on Windows.
            import os
            import tempfile
            steps[1].screenshot_path = os.path.join(tempfile.gettempdir(), "shot.png")
        return Walkthrough(title="Sample", description="A demo flow", steps=steps)

    def test_markdown_has_steps(self):
        md = render_markdown(self._wt())
        self.assertIn("# Sample", md)
        self.assertIn("Step 1. Visit the site.", md)
        self.assertIn("Step 2. Click the button.", md)
        self.assertIn("`WR_to_url`", md)

    def test_markdown_embeds_data_uri(self):
        md = render_markdown(self._wt(with_image=True))
        self.assertIn("data:image/png;base64,deadbeef", md)

    def test_markdown_uses_path_when_no_embed(self):
        import os
        import tempfile
        expected = os.path.join(tempfile.gettempdir(), "shot.png")
        md = render_markdown(self._wt(with_image=True), embed_images=False)
        self.assertIn(expected, md)
        self.assertNotIn("data:image", md)

    def test_confluence_xml_escapes(self):
        wt = Walkthrough(title="<bad>", steps=[
            WalkthroughStep(index=0, action_command="WR_to_url",
                            kwargs={"url": "https://x"}, narration="A & B"),
        ])
        x = render_confluence(wt)
        self.assertIn("&lt;bad&gt;", x)
        self.assertIn("A &amp; B", x)

    def test_confluence_uses_attachment_for_image(self):
        wt = self._wt(with_image=True)
        x = render_confluence(wt)
        self.assertIn('ri:filename="shot.png"', x)


class TestBuildWalkthrough(unittest.TestCase):

    def tearDown(self):
        set_llm_callable(None)

    def test_no_narrate(self):
        wt = build_walkthrough("login", SAMPLE_ACTIONS, narrate=False)
        self.assertEqual(wt.title, "login")
        self.assertTrue(all(s.narration == "" for s in wt.steps))

    def test_with_narrate(self):
        narrations = json.dumps({"steps": ["a"] * 100})
        set_llm_callable(lambda _p: narrations)
        wt = build_walkthrough("login", SAMPLE_ACTIONS, narrate=True)
        self.assertTrue(any(s.narration for s in wt.steps))


class TestSaveWalkthrough(unittest.TestCase):

    def test_markdown_file(self):
        wt = Walkthrough(title="x", steps=[
            WalkthroughStep(index=0, action_command="WR_x", narration="n"),
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_walkthrough(wt, Path(tmpdir) / "out.md")
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("# x", text)

    def test_confluence_file(self):
        wt = Walkthrough(title="x", steps=[
            WalkthroughStep(index=0, action_command="WR_x", narration="n"),
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_walkthrough(wt, Path(tmpdir) / "out.xml", fmt="confluence")
            text = path.read_text(encoding="utf-8")
            self.assertIn("<h1>x</h1>", text)

    def test_unknown_fmt_raises(self):
        wt = Walkthrough(title="x")
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(WalkthroughError):
                save_walkthrough(wt, Path(tmpdir) / "out.x", fmt="rst")


if __name__ == "__main__":
    unittest.main()
