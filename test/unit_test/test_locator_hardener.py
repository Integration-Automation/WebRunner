"""Unit tests for je_web_runner.utils.locator_hardener."""
import json
import unittest

from je_web_runner.utils.locator_hardener.hardener import (
    FragileLocator,
    LocatorHardenerError,
    LocatorStrategy,
    LocatorSuggestion,
    build_prompt,
    harden,
    parse_suggestions,
    score_fragility,
)


class StubClient:
    def __init__(self, response):
        self.response = response
        self.last_prompt = None

    def suggest(self, prompt):
        self.last_prompt = prompt
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _good_response():
    return json.dumps([
        {"strategy": "id", "value": "submit-btn",
         "rationale": "id is unique and stable"},
        {"strategy": "css selector", "value": "[data-test=submit]",
         "rationale": "stable test attribute"},
    ])


class TestFragileLocator(unittest.TestCase):

    def test_rejects_empty(self):
        with self.assertRaises(LocatorHardenerError):
            FragileLocator(test_id="", strategy=LocatorStrategy.CSS, value="x")
        with self.assertRaises(LocatorHardenerError):
            FragileLocator(test_id="t", strategy=LocatorStrategy.CSS, value="")

    def test_rejects_negative_history(self):
        with self.assertRaises(LocatorHardenerError):
            FragileLocator(test_id="t", strategy=LocatorStrategy.CSS, value="x",
                           failure_history=-1)


class TestScoreFragility(unittest.TestCase):

    def test_id_is_low(self):
        score = score_fragility(FragileLocator(
            test_id="t", strategy=LocatorStrategy.ID, value="submit",
        ))
        self.assertLess(score.score, 0.5)

    def test_xpath_with_text_high(self):
        score = score_fragility(FragileLocator(
            test_id="t", strategy=LocatorStrategy.XPATH,
            value="//button[text()='Submit']",
        ))
        self.assertGreater(score.score, 0.4)
        self.assertTrue(any("text" in r for r in score.reasons))

    def test_nth_of_type_high(self):
        score = score_fragility(FragileLocator(
            test_id="t", strategy=LocatorStrategy.CSS,
            value=".table tr:nth-of-type(3) td",
        ))
        self.assertGreaterEqual(score.score, 0.4)
        self.assertTrue(any("nth-of-type" in r for r in score.reasons))

    def test_hashed_class(self):
        score = score_fragility(FragileLocator(
            test_id="t", strategy=LocatorStrategy.CSS,
            value=".Button_button-_a1b2c3",
        ))
        self.assertTrue(any("hashed" in r for r in score.reasons))

    def test_failure_history_boost(self):
        score = score_fragility(FragileLocator(
            test_id="t", strategy=LocatorStrategy.ID, value="x",
            failure_history=5,
        ))
        self.assertTrue(any("failed" in r for r in score.reasons))

    def test_class_name_with_spaces(self):
        score = score_fragility(FragileLocator(
            test_id="t", strategy=LocatorStrategy.CLASS_NAME,
            value="btn primary",
        ))
        self.assertTrue(any("multi-class" in r for r in score.reasons))

    def test_rejects_non_locator(self):
        with self.assertRaises(LocatorHardenerError):
            score_fragility("nope")  # type: ignore[arg-type]


class TestBuildPrompt(unittest.TestCase):

    def test_includes_locator(self):
        prompt = build_prompt(FragileLocator(
            test_id="login.json", strategy=LocatorStrategy.CSS,
            value=".x .y nth-of-type(2)", dom_excerpt="<form>...</form>",
        ))
        self.assertIn("login.json", prompt)
        self.assertIn(".x .y nth-of-type(2)", prompt)
        self.assertIn("<form>", prompt)

    def test_rejects_non_locator(self):
        with self.assertRaises(LocatorHardenerError):
            build_prompt("nope")  # type: ignore[arg-type]


class TestParseSuggestions(unittest.TestCase):

    def test_parses_clean(self):
        suggestions = parse_suggestions(_good_response())
        self.assertEqual(len(suggestions), 2)
        self.assertEqual(suggestions[0].strategy, LocatorStrategy.ID)

    def test_drops_unsafe_nth(self):
        raw = json.dumps([
            {"strategy": "css selector",
             "value": "tr:nth-of-type(2)", "rationale": "x"},
            {"strategy": "id", "value": "good", "rationale": "y"},
        ])
        suggestions = parse_suggestions(raw)
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].value, "good")

    def test_drops_unsafe_xpath_text(self):
        raw = json.dumps([
            {"strategy": "xpath",
             "value": "//button[text()='Save']", "rationale": "x"},
            {"strategy": "id", "value": "save", "rationale": "y"},
        ])
        suggestions = parse_suggestions(raw)
        self.assertEqual(suggestions[0].strategy, LocatorStrategy.ID)

    def test_extracts_from_text(self):
        wrapped = "Here you go: " + _good_response() + " thanks"
        self.assertEqual(len(parse_suggestions(wrapped)), 2)

    def test_skip_unknown_strategy(self):
        raw = json.dumps([
            {"strategy": "fancy", "value": "x", "rationale": "y"},
            {"strategy": "id", "value": "good", "rationale": "y"},
        ])
        self.assertEqual(len(parse_suggestions(raw)), 1)

    def test_skip_non_dict(self):
        raw = json.dumps([
            "not a dict",
            {"strategy": "id", "value": "good", "rationale": "y"},
        ])
        self.assertEqual(len(parse_suggestions(raw)), 1)

    def test_skip_empty_value(self):
        raw = json.dumps([
            {"strategy": "id", "value": "", "rationale": "y"},
            {"strategy": "id", "value": "good", "rationale": "y"},
        ])
        self.assertEqual(len(parse_suggestions(raw)), 1)

    def test_no_valid_raises(self):
        raw = json.dumps([{"strategy": "fancy", "value": "x", "rationale": ""}])
        with self.assertRaises(LocatorHardenerError):
            parse_suggestions(raw)

    def test_empty(self):
        with self.assertRaises(LocatorHardenerError):
            parse_suggestions("")

    def test_no_array(self):
        with self.assertRaises(LocatorHardenerError):
            parse_suggestions("just text")

    def test_bad_json(self):
        with self.assertRaises(LocatorHardenerError):
            parse_suggestions("[not json]")


class TestHarden(unittest.TestCase):

    def test_skips_when_below_threshold(self):
        locator = FragileLocator(
            test_id="t", strategy=LocatorStrategy.ID, value="x",
        )
        client = StubClient(_good_response())
        result = harden(locator, client, min_fragility=0.5)
        self.assertEqual(result, [])
        self.assertIsNone(client.last_prompt)

    def test_calls_when_fragile(self):
        locator = FragileLocator(
            test_id="t", strategy=LocatorStrategy.CSS,
            value=".a .b .c .d:nth-of-type(2)",
        )
        result = harden(locator, StubClient(_good_response()), min_fragility=0.3)
        self.assertGreaterEqual(len(result), 1)

    def test_client_error_wrapped(self):
        locator = FragileLocator(
            test_id="t", strategy=LocatorStrategy.CSS,
            value=".a:nth-of-type(2)",
        )
        with self.assertRaises(LocatorHardenerError):
            harden(locator, StubClient(RuntimeError("rate limit")),
                   min_fragility=0.3)

    def test_bad_threshold(self):
        locator = FragileLocator(
            test_id="t", strategy=LocatorStrategy.CSS, value=".a",
        )
        with self.assertRaises(LocatorHardenerError):
            harden(locator, StubClient(_good_response()), min_fragility=2.0)


class TestSuggestionDict(unittest.TestCase):

    def test_to_dict(self):
        s = LocatorSuggestion(strategy=LocatorStrategy.ID, value="x", rationale="y")
        self.assertEqual(s.to_dict()["strategy"], "id")


if __name__ == "__main__":
    unittest.main()
