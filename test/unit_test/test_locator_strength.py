import unittest

from je_web_runner.utils.linter.locator_strength import (
    LocatorStrengthError,
    assert_strength,
    score_action_locators,
    score_locator,
    weakest,
)


class TestScoreLocator(unittest.TestCase):

    def test_id_scores_high(self):
        result = score_locator("ID", "submit-btn")
        self.assertGreaterEqual(result.score, 90)

    def test_auto_generated_id_drops_score(self):
        result = score_locator("ID", "row-0123456789ab")
        self.assertLess(result.score, 80)

    def test_css_with_test_id_scores_high(self):
        result = score_locator("CSS_SELECTOR", "[data-testid='login']")
        self.assertGreaterEqual(result.score, 85)

    def test_deep_xpath_loses_points(self):
        result = score_locator(
            "XPATH",
            "/html/body/div/div/div/div/section/article/p"
        )
        self.assertLess(result.score, 50)

    def test_text_based_xpath_flagged(self):
        result = score_locator("XPATH", "//button[contains(text(), 'Login')]")
        self.assertIn("text-based xpath is locale-fragile", result.reasons)

    def test_tag_name_low(self):
        result = score_locator("TAG_NAME", "div")
        self.assertLess(result.score, 30)

    def test_unknown_strategy_raises(self):
        with self.assertRaises(LocatorStrengthError):
            score_locator("MAGIC", "anything")


class TestScoreActionLocators(unittest.TestCase):

    def test_extracts_and_scores(self):
        actions = [
            ["WR_save_test_object", {"test_object_name": "submit", "object_type": "ID"}],
            ["WR_save_test_object", {"test_object_name": "div", "object_type": "TAG_NAME"}],
        ]
        findings = score_action_locators(actions)
        self.assertEqual(len(findings), 2)
        self.assertGreater(findings[0]["score"], findings[1]["score"])

    def test_weakest_filter(self):
        findings = [
            {"score": 90}, {"score": 30}, {"score": 60},
        ]
        bad = weakest(findings, threshold=50)
        self.assertEqual(len(bad), 1)

    def test_assert_strength_raises_on_low(self):
        actions = [["WR_save_test_object", {"test_object_name": "x", "object_type": "TAG_NAME"}]]
        findings = score_action_locators(actions)
        with self.assertRaises(LocatorStrengthError):
            assert_strength(findings, minimum=80)


if __name__ == "__main__":
    unittest.main()
