import unittest

from je_web_runner.utils.ai_assist.llm_assist import (
    LLMAssistError,
    explain_failure,
    generate_actions_from_prompt,
    has_llm_callable,
    llm_self_heal_locator,
    set_llm_callable,
    suggest_locator,
)


class TestLLMRegistration(unittest.TestCase):

    def setUp(self):
        set_llm_callable(None)

    def tearDown(self):
        set_llm_callable(None)

    def test_unregistered_raises(self):
        self.assertFalse(has_llm_callable())
        with self.assertRaises(LLMAssistError):
            suggest_locator("<html/>", "submit button")

    def test_register_then_use(self):
        set_llm_callable(lambda prompt: '{"strategy": "ID", "value": "submit"}')
        self.assertTrue(has_llm_callable())
        result = suggest_locator("<html/>", "submit button")
        self.assertEqual(result, {"strategy": "ID", "value": "submit"})

    def test_non_string_response_raises(self):
        set_llm_callable(lambda prompt: 42)
        with self.assertRaises(LLMAssistError):
            suggest_locator("<html/>", "x")

    def test_unparsable_response_raises(self):
        set_llm_callable(lambda prompt: "no json here")
        with self.assertRaises(LLMAssistError):
            suggest_locator("<html/>", "x")

    def test_missing_keys_in_locator_raises(self):
        set_llm_callable(lambda prompt: '{"strategy": "ID"}')
        with self.assertRaises(LLMAssistError):
            suggest_locator("<html/>", "x")


class TestGenerateActions(unittest.TestCase):

    def setUp(self):
        set_llm_callable(None)

    def tearDown(self):
        set_llm_callable(None)

    def test_returns_parsed_array(self):
        set_llm_callable(
            lambda prompt: '[["WR_to_url", {"url": "https://e.com"}], ["WR_quit_all"]]'
        )
        result = generate_actions_from_prompt("go to e.com and quit")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], "WR_to_url")
        self.assertEqual(result[1][0], "WR_quit_all")

    def test_non_array_raises(self):
        set_llm_callable(lambda prompt: '{"not": "array"}')
        with self.assertRaises(LLMAssistError):
            generate_actions_from_prompt("x")


class TestSelfHealLocator(unittest.TestCase):

    def setUp(self):
        set_llm_callable(None)

    def tearDown(self):
        set_llm_callable(None)

    def test_uses_html_provider(self):
        captured = {}

        def html_provider():
            captured["called"] = True
            return "<html><button id='go'/></html>"

        set_llm_callable(lambda prompt: '{"strategy": "ID", "value": "go"}')
        result = llm_self_heal_locator("submit", html_provider)
        self.assertTrue(captured["called"])
        self.assertEqual(result["value"], "go")


class TestExplainFailure(unittest.TestCase):

    def setUp(self):
        set_llm_callable(None)

    def tearDown(self):
        set_llm_callable(None)

    def test_parses_rca_payload(self):
        set_llm_callable(lambda prompt: (
            '{"likely_cause": "stale element",'
            ' "evidence": ["DOM mutated mid-click"],'
            ' "next_steps": ["add wait_for_selector"],'
            ' "confidence": 0.7}'
        ))
        rca = explain_failure(
            test_name="login_test",
            error_repr="StaleElementReferenceException",
            console=[{"type": "error", "text": "uncaught"}],
            network=[{"url": "/api/x", "status": 200}],
            steps=[["WR_element_click"]],
        )
        self.assertEqual(rca["likely_cause"], "stale element")
        self.assertEqual(rca["confidence"], 0.7)

    def test_missing_keys_raises(self):
        set_llm_callable(lambda prompt: '{"likely_cause": "x"}')
        with self.assertRaises(LLMAssistError):
            explain_failure("t", "boom")


if __name__ == "__main__":
    unittest.main()
