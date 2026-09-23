import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.geo_locale import (
    GeoLocaleError,
    GeoOverride,
    apply_overrides,
    cdp_payloads,
    playwright_context_kwargs,
)


class TestValidation(unittest.TestCase):

    def test_lat_lon_must_pair(self):
        geo_override = GeoOverride(latitude=51.5)
        with self.assertRaises(GeoLocaleError):
            geo_override.validate()

    def test_lat_out_of_range(self):
        geo_override = GeoOverride(latitude=200.0, longitude=0.0)
        with self.assertRaises(GeoLocaleError):
            geo_override.validate()

    def test_invalid_timezone(self):
        geo_override = GeoOverride(timezone="GMT+1")
        with self.assertRaises(GeoLocaleError):
            geo_override.validate()

    def test_locale_too_short(self):
        geo_override = GeoOverride(locale="x")
        with self.assertRaises(GeoLocaleError):
            geo_override.validate()


class TestPayloads(unittest.TestCase):

    def test_cdp_payloads_lists_all(self):
        override = GeoOverride(
            latitude=25.03, longitude=121.56, timezone="Asia/Taipei", locale="zh-TW",
        )
        methods = [p["method"] for p in cdp_payloads(override)]
        self.assertIn("Emulation.setGeolocationOverride", methods)
        self.assertIn("Emulation.setTimezoneOverride", methods)
        self.assertIn("Emulation.setLocaleOverride", methods)

    def test_playwright_kwargs(self):
        override = GeoOverride(
            latitude=51.5, longitude=-0.13, timezone="Europe/London", locale="en-GB",
        )
        kwargs = playwright_context_kwargs(override)
        self.assertEqual(kwargs["timezone_id"], "Europe/London")
        self.assertEqual(kwargs["locale"], "en-GB")
        self.assertIn("geolocation", kwargs)
        self.assertIn("geolocation", kwargs["permissions"])

    def test_only_locale_payload(self):
        override = GeoOverride(locale="ja-JP")
        kwargs = playwright_context_kwargs(override)
        self.assertEqual(kwargs, {"locale": "ja-JP"})


class TestApplyOverrides(unittest.TestCase):

    def test_applies_all(self):
        driver = MagicMock()
        override = GeoOverride(
            latitude=0.0, longitude=0.0, timezone="UTC/UTC", locale="en-US",
        )
        # The validator requires "/" in timezone — UTC/UTC keeps it shape-OK.
        methods = apply_overrides(driver, override)
        self.assertEqual(driver.execute_cdp_cmd.call_count, len(methods))

    def test_unsupported_driver_raises(self):
        object_value = object()
        geo_override = GeoOverride(locale="en-US")
        with self.assertRaises(GeoLocaleError):
            apply_overrides(object_value, geo_override)


if __name__ == "__main__":
    unittest.main()
