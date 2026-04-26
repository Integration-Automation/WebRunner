import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.driver_dispatch import (
    DriverDispatchError,
    evaluate_expression,
    run_script,
)


class TestEvaluateExpression(unittest.TestCase):

    def test_selenium_path(self):
        driver = MagicMock()
        driver.execute_script.return_value = 42
        result = evaluate_expression(driver, "1 + 41")
        self.assertEqual(result, 42)
        driver.execute_script.assert_called_once_with("return 1 + 41;")

    def test_playwright_path(self):
        page = MagicMock(spec=["evaluate"])
        page.evaluate.return_value = 42
        result = evaluate_expression(page, "1 + 41")
        self.assertEqual(result, 42)
        page.evaluate.assert_called_once_with("() => 1 + 41")

    def test_unsupported_driver(self):
        with self.assertRaises(DriverDispatchError):
            evaluate_expression(object(), "x")

    def test_empty_expression_raises(self):
        with self.assertRaises(DriverDispatchError):
            evaluate_expression(MagicMock(), "")


class TestRunScript(unittest.TestCase):

    def test_selenium_with_args(self):
        driver = MagicMock()
        driver.execute_script.return_value = "ok"
        run_script(driver, "return arguments[0]", "hello")
        driver.execute_script.assert_called_once_with("return arguments[0]", "hello")

    def test_playwright_no_args(self):
        page = MagicMock(spec=["evaluate"])
        run_script(page, "() => 1")
        page.evaluate.assert_called_once_with("() => 1")

    def test_playwright_single_arg(self):
        page = MagicMock(spec=["evaluate"])
        run_script(page, "(x) => x", "value")
        page.evaluate.assert_called_once_with("(x) => x", "value")

    def test_playwright_multi_args_bundled(self):
        page = MagicMock(spec=["evaluate"])
        run_script(page, "(args) => args", "a", "b", "c")
        page.evaluate.assert_called_once_with("(args) => args", ["a", "b", "c"])

    def test_unsupported_driver(self):
        with self.assertRaises(DriverDispatchError):
            run_script(object(), "() => 1")

    def test_empty_body(self):
        with self.assertRaises(DriverDispatchError):
            run_script(MagicMock(), "")


if __name__ == "__main__":
    unittest.main()
