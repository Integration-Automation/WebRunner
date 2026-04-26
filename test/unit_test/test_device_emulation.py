import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.device_emulation import (
    DeviceEmulationError,
    DevicePreset,
    apply_to_chrome_options,
    available_presets,
    get_preset,
    playwright_kwargs,
)
from je_web_runner.utils.device_emulation.presets import (
    cdp_emulation_command,
    register_preset,
)


class TestPresets(unittest.TestCase):

    def test_iphone_15_pro_loads(self):
        preset = get_preset("iPhone 15 Pro")
        self.assertEqual(preset.width, 393)
        self.assertTrue(preset.is_mobile)

    def test_unknown_preset_raises(self):
        with self.assertRaises(DeviceEmulationError):
            get_preset("Galaxy Foldable Z100")

    def test_available_includes_known(self):
        self.assertIn("Pixel 8", available_presets())

    def test_register_preset_overwrites(self):
        register_preset(DevicePreset(
            name="Pixel 8",
            width=999, height=999, device_scale_factor=1.0,
            is_mobile=False, has_touch=False, user_agent="ua",
        ))
        self.assertEqual(get_preset("Pixel 8").width, 999)

    def test_register_preset_rejects_non_preset(self):
        with self.assertRaises(DeviceEmulationError):
            register_preset("not-a-preset")  # type: ignore[arg-type]


class TestPlaywrightKwargs(unittest.TestCase):

    def test_returns_complete_payload(self):
        kwargs = playwright_kwargs("iPad Pro 11")
        self.assertEqual(kwargs["viewport"], {"width": 834, "height": 1194})
        self.assertTrue(kwargs["is_mobile"])
        self.assertTrue(kwargs["has_touch"])
        self.assertIn("iPad", kwargs["user_agent"])


class TestChromeOptions(unittest.TestCase):

    def test_applies_args(self):
        options = MagicMock()
        apply_to_chrome_options(options, "Desktop 1080p")
        args = [c.args[0] for c in options.add_argument.call_args_list]
        self.assertTrue(any("--window-size=1920,1080" in a for a in args))
        self.assertTrue(any("--user-agent=" in a for a in args))

    def test_invalid_options_object_raises(self):
        with self.assertRaises(DeviceEmulationError):
            apply_to_chrome_options(object(), "iPhone SE")


class TestCdpCommand(unittest.TestCase):

    def test_payload_shape(self):
        payload = cdp_emulation_command("iPhone SE")
        self.assertTrue(payload["mobile"])
        self.assertEqual(payload["deviceScaleFactor"], 2.0)


if __name__ == "__main__":
    unittest.main()
