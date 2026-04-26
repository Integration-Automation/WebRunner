import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.appium_integration.gestures import (
    AppiumGestureError,
    Point,
    double_tap,
    long_press,
    pinch,
    scroll,
    swipe,
)


def _named_only_driver():
    """Driver that supports only the mobile: extension."""
    driver = MagicMock(spec=["execute_script"])
    driver.execute_script = MagicMock(return_value=None)
    return driver


def _w3c_only_driver():
    """Driver without the mobile: extension; only W3C perform_actions."""
    driver = MagicMock(spec=["execute_script", "perform_actions"])
    driver.execute_script = MagicMock(side_effect=RuntimeError("no extension"))
    driver.perform_actions = MagicMock()
    return driver


class TestSwipe(unittest.TestCase):

    def test_named_extension_path(self):
        driver = _named_only_driver()
        swipe(driver, Point(10, 10), Point(100, 10))
        args = driver.execute_script.call_args.args
        self.assertEqual(args[0], "mobile: swipeGesture")
        self.assertEqual(args[1]["direction"], "right")

    def test_w3c_fallback_path(self):
        driver = _w3c_only_driver()
        swipe(driver, Point(0, 0), Point(0, 200))
        driver.perform_actions.assert_called_once()
        actions = driver.perform_actions.call_args.args[0]
        self.assertEqual(actions[0]["type"], "pointer")

    def test_invalid_duration(self):
        with self.assertRaises(AppiumGestureError):
            swipe(_named_only_driver(), Point(0, 0), Point(0, 1), duration_ms=0)


class TestScroll(unittest.TestCase):

    def test_invalid_direction(self):
        with self.assertRaises(AppiumGestureError):
            scroll(_named_only_driver(), "diagonal")

    def test_invalid_percent(self):
        with self.assertRaises(AppiumGestureError):
            scroll(_named_only_driver(), "up", percent=0)

    def test_named_extension(self):
        driver = _named_only_driver()
        scroll(driver, "down", rect=(0, 0, 400, 800))
        args = driver.execute_script.call_args.args
        self.assertEqual(args[0], "mobile: scrollGesture")

    def test_fallback_synthesizes_swipe(self):
        driver = _w3c_only_driver()
        scroll(driver, "down")
        driver.perform_actions.assert_called_once()


class TestLongPress(unittest.TestCase):

    def test_named_extension(self):
        driver = _named_only_driver()
        long_press(driver, Point(50, 50))
        args = driver.execute_script.call_args.args
        self.assertEqual(args[0], "mobile: longClickGesture")

    def test_fallback_pause(self):
        driver = _w3c_only_driver()
        long_press(driver, Point(50, 50), duration_ms=500)
        actions = driver.perform_actions.call_args.args[0]
        sub = actions[0]["actions"]
        self.assertTrue(any(a["type"] == "pause" and a["duration"] == 500 for a in sub))

    def test_invalid_duration(self):
        with self.assertRaises(AppiumGestureError):
            long_press(_named_only_driver(), Point(0, 0), duration_ms=0)


class TestPinch(unittest.TestCase):

    def test_zoom_in_named_extension(self):
        driver = _named_only_driver()
        pinch(driver, rect=(0, 0, 200, 200), scale=2.0)
        args = driver.execute_script.call_args.args
        self.assertEqual(args[0], "mobile: pinchOpenGesture")

    def test_zoom_out_named_extension(self):
        driver = _named_only_driver()
        pinch(driver, rect=(0, 0, 200, 200), scale=0.5)
        args = driver.execute_script.call_args.args
        self.assertEqual(args[0], "mobile: pinchCloseGesture")

    def test_invalid_scale(self):
        with self.assertRaises(AppiumGestureError):
            pinch(_named_only_driver(), rect=(0, 0, 1, 1), scale=0)

    def test_w3c_two_finger_fallback(self):
        driver = _w3c_only_driver()
        pinch(driver, rect=(0, 0, 200, 200), scale=2.0)
        actions = driver.perform_actions.call_args.args[0]
        self.assertEqual(len(actions), 2)


class TestDoubleTap(unittest.TestCase):

    def test_named_extension(self):
        driver = _named_only_driver()
        double_tap(driver, Point(20, 20))
        args = driver.execute_script.call_args.args
        self.assertEqual(args[0], "mobile: doubleClickGesture")

    def test_fallback_emits_two_downs(self):
        driver = _w3c_only_driver()
        double_tap(driver, Point(20, 20))
        sub = driver.perform_actions.call_args.args[0][0]["actions"]
        downs = [a for a in sub if a.get("type") == "pointerDown"]
        self.assertEqual(len(downs), 2)


class TestUnsupportedDriver(unittest.TestCase):

    def test_swipe_without_either_capability(self):
        driver = MagicMock(spec=[])
        with self.assertRaises(AppiumGestureError):
            swipe(driver, Point(0, 0), Point(1, 1))


if __name__ == "__main__":
    unittest.main()
