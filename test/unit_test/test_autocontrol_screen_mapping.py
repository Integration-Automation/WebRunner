"""Page → screen coordinates, and ``WR_ac_click_element_native`` with AutoControl faked."""
import unittest
from unittest.mock import MagicMock, patch

from selenium.webdriver.chromium.webdriver import ChromiumDriver

from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.mcp_server import _policy
from je_web_runner.utils.autocontrol_bridge import native
from je_web_runner.utils.autocontrol_bridge.bridge import AutoControlBridgeError
from je_web_runner.utils.autocontrol_bridge.screen_mapping import ScreenMappingError, element_center_on_screen
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

# Chrome maximized on a 100 % 1920x1080 monitor: the invisible 8 px resize border puts the
# window at (-8, -8), and the tab strip and toolbar take the top 87 px of the viewport's frame.
_MAXIMIZED = {"screenX": -8, "screenY": -8, "outerWidth": 1936, "outerHeight": 1056,
              "innerWidth": 1920, "innerHeight": 953, "devicePixelRatio": 1.0,
              "left": 100, "top": 200, "width": 50, "height": 20}


def _metrics(**changes):
    return {**_MAXIMIZED, **changes}


class TestMapping(unittest.TestCase):

    def test_maximized_at_100_percent(self):
        # side border 8, frame above the viewport 1056 - 953 - 8 = 95; centre (125, 210)
        self.assertEqual(element_center_on_screen(_metrics()), (125, 297))

    def test_display_scale_multiplies_screen_pixels(self):
        # 150 %: screen pixels are device-independent, the mouse takes 1.5 per pixel
        metrics = _metrics(screenX=100, screenY=50, outerWidth=1216, innerWidth=1200, outerHeight=900,
                           innerHeight=800, devicePixelRatio=1.5, left=40, top=30, width=40, height=20)
        # x: (100 + 8 + 60) * 1.5, y: (50 + 92 + 40) * 1.5
        self.assertEqual(element_center_on_screen(metrics), (252, 273))

    def test_page_zoom_with_an_explicit_display_scale(self):
        # 200 % page zoom on a 100 % monitor: the 1920-pixel viewport is 960 CSS pixels wide
        metrics = _metrics(screenX=0, screenY=0, innerWidth=960, innerHeight=476.5, devicePixelRatio=2.0,
                           left=90, top=40, width=20, height=20)
        # x: 0 + (1936 - 1920) / 2 + 100 * 2; y: (1056 - 953 - 8) + 50 * 2
        self.assertEqual(element_center_on_screen(metrics, scale=1.0), (208, 195))

    def test_unplaceable_elements_raise(self):
        cases = (_metrics(width=0), _metrics(top=2000), _metrics(left=-100),
                 {key: value for key, value in _MAXIMIZED.items() if key != "screenX"},
                 _metrics(devicePixelRatio=0))
        for metrics in cases:
            with self.subTest(metrics=metrics), self.assertRaises(ScreenMappingError):
                element_center_on_screen(metrics)
        with self.assertRaises(ScreenMappingError):
            element_center_on_screen(_metrics(), scale=-1)

    def test_the_error_is_a_bridge_error(self):
        self.assertTrue(issubclass(ScreenMappingError, AutoControlBridgeError))


class TestClickElementNative(unittest.TestCase):

    def setUp(self):
        self.driver = MagicMock(spec=ChromiumDriver)
        self.driver.capabilities = {}
        self.driver.execute_script.side_effect = lambda script, *args: (
            "Mozilla/5.0 Chrome/140" if "userAgent" in script else _metrics())
        for target, attribute, value in ((webdriver_wrapper_instance, "current_webdriver", self.driver),
                                         (web_element_wrapper, "current_web_element", MagicMock())):
            previous = getattr(target, attribute)
            setattr(target, attribute, value)
            self.addCleanup(setattr, target, attribute, previous)
        patcher = patch.object(native, "ac_run")
        self.ac_run = patcher.start()
        self.addCleanup(patcher.stop)

    def test_clicks_the_current_element_at_its_screen_centre(self):
        self.assertEqual(native.click_element_native(), [125, 297])
        self.ac_run.assert_called_once_with(["AC_click_mouse", {"mouse_keycode": "mouse_left", "x": 125, "y": 297}])
        _script, element = self.driver.execute_script.call_args.args
        self.assertIs(element, web_element_wrapper.current_web_element)

    def test_a_selector_finds_the_element_first(self):
        native.click_element_native("#submit", mouse_button="mouse_right")
        self.driver.find_element.assert_called_once_with("css selector", "#submit")
        self.assertEqual(self.ac_run.call_args.args[0][1]["mouse_keycode"], "mouse_right")

    def test_refusals(self):
        web_element_wrapper.current_web_element = None
        with self.assertRaisesRegex(AutoControlBridgeError, "selector"):
            native.click_element_native()
        self.driver.execute_script.side_effect = lambda script, *args: "HeadlessChrome/140"
        with self.assertRaisesRegex(AutoControlBridgeError, "headless"):
            native.click_element_native("#submit")
        webdriver_wrapper_instance.current_webdriver = None
        with self.assertRaisesRegex(AutoControlBridgeError, "no Selenium driver"):
            native.click_element_native("#submit")
        self.ac_run.assert_not_called()

    def test_registered_and_denied_over_mcp(self):
        self.assertIn("WR_ac_click_element_native", executor.event_dict)
        self.assertIn("WR_ac_click_element_native", _policy.UNSAFE_COMMANDS)


if __name__ == "__main__":
    unittest.main()
