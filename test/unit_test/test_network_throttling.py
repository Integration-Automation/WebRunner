import unittest
from unittest.mock import patch

from je_web_runner.utils.network_emulation.throttling import (
    NetworkEmulationError,
    list_presets,
    playwright_emulate_network,
    selenium_emulate_network,
    selenium_clear_throttling,
)


class TestPresets(unittest.TestCase):

    def test_known_presets_listed(self):
        names = list_presets()
        for required in ("offline", "slow_3g", "fast_3g", "regular_4g", "wifi", "no_throttling"):
            self.assertIn(required, names)

    def test_unknown_preset_raises(self):
        with patch("je_web_runner.utils.network_emulation.throttling.selenium_cdp"):
            with self.assertRaises(NetworkEmulationError):
                selenium_emulate_network("dial_up")


class TestSelenium(unittest.TestCase):

    def test_emulate_dispatches_cdp_with_params(self):
        with patch("je_web_runner.utils.network_emulation.throttling.selenium_cdp") as cdp:
            selenium_emulate_network("slow_3g")
            method, params = cdp.call_args.args
            self.assertEqual(method, "Network.emulateNetworkConditions")
            self.assertEqual(params["latency"], 400)
            self.assertGreater(params["downloadThroughput"], 0)
            self.assertFalse(params["offline"])

    def test_offline_preset_sets_flag(self):
        with patch("je_web_runner.utils.network_emulation.throttling.selenium_cdp") as cdp:
            selenium_emulate_network("offline")
            params = cdp.call_args.args[1]
            self.assertTrue(params["offline"])

    def test_clear_uses_no_throttling(self):
        with patch("je_web_runner.utils.network_emulation.throttling.selenium_cdp") as cdp:
            selenium_clear_throttling()
            params = cdp.call_args.args[1]
            self.assertEqual(params["downloadThroughput"], -1)


class TestPlaywright(unittest.TestCase):

    def test_emulate_dispatches_via_playwright_cdp(self):
        with patch("je_web_runner.utils.network_emulation.throttling.playwright_cdp") as cdp:
            playwright_emulate_network("fast_3g")
            method, params = cdp.call_args.args
            self.assertEqual(method, "Network.emulateNetworkConditions")
            self.assertEqual(params["latency"], 150)


if __name__ == "__main__":
    unittest.main()
