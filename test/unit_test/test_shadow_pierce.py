import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.dom_traversal.shadow_pierce import (
    ShadowPierceError,
    assert_pierced_visible,
    find_all,
    find_first,
)


class TestFindFirst(unittest.TestCase):

    def test_calls_execute_script_on_selenium(self):
        driver = MagicMock()
        driver.execute_script.return_value = "fake-element"
        result = find_first(driver, "button.primary")
        self.assertEqual(result, "fake-element")
        # Selector must be passed as the first arg
        args = driver.execute_script.call_args
        self.assertEqual(args.args[1], "button.primary")

    def test_evaluate_path_for_playwright(self):
        page = MagicMock(spec=["evaluate"])
        page.evaluate.return_value = "fake-element"
        result = find_first(page, "button.primary")
        self.assertEqual(result, "fake-element")
        page.evaluate.assert_called_once()

    def test_unsupported_driver_raises(self):
        with self.assertRaises(ShadowPierceError):
            find_first(object(), "x")

    def test_empty_selector_raises(self):
        with self.assertRaises(ShadowPierceError):
            find_first(MagicMock(), "")


class TestFindAll(unittest.TestCase):

    def test_returns_list(self):
        driver = MagicMock()
        driver.execute_script.return_value = ["a", "b"]
        self.assertEqual(find_all(driver, ".item"), ["a", "b"])

    def test_none_returns_empty(self):
        driver = MagicMock()
        driver.execute_script.return_value = None
        self.assertEqual(find_all(driver, ".item"), [])

    def test_invalid_limit_raises(self):
        with self.assertRaises(ShadowPierceError):
            find_all(MagicMock(), ".item", limit=0)


class TestAssertPiercedVisible(unittest.TestCase):

    def test_passes_when_present(self):
        driver = MagicMock()
        driver.execute_script.return_value = "exists"
        assert_pierced_visible(driver, "button.primary")

    def test_raises_when_missing(self):
        driver = MagicMock()
        driver.execute_script.return_value = None
        with self.assertRaises(ShadowPierceError):
            assert_pierced_visible(driver, "button.primary")


if __name__ == "__main__":
    unittest.main()
