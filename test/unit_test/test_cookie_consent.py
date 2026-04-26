import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.cookie_consent import (
    ConsentBannerError,
    ConsentDismisser,
    common_dismiss_selectors,
    register_selector,
)


class TestConsentDismisser(unittest.TestCase):

    def test_clicks_first_matching_selector(self):
        driver = MagicMock()
        # First selector miss, second matches
        driver.execute_script.side_effect = [False, True]
        dismisser = ConsentDismisser(selectors=["#a", "#b", "#c"])
        clicked = dismisser.dismiss(driver)
        self.assertEqual(clicked, "#b")

    def test_returns_none_when_no_match(self):
        driver = MagicMock()
        driver.execute_script.return_value = False
        dismisser = ConsentDismisser(selectors=["#a"])
        self.assertIsNone(dismisser.dismiss(driver))

    def test_unsupported_driver_raises(self):
        with self.assertRaises(ConsentBannerError):
            ConsentDismisser(selectors=["#x"]).dismiss(object())

    def test_default_selectors_present(self):
        defaults = common_dismiss_selectors()
        self.assertIn("#onetrust-accept-btn-handler", defaults)

    def test_register_selector_idempotent(self):
        before = len(common_dismiss_selectors())
        register_selector("#new-banner-button")
        register_selector("#new-banner-button")
        self.assertEqual(len(common_dismiss_selectors()), before + 1)
        with self.assertRaises(ConsentBannerError):
            register_selector("")


if __name__ == "__main__":
    unittest.main()
