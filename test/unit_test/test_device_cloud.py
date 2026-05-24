"""Unit tests for je_web_runner.utils.device_cloud."""
import os
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.device_cloud.real_device import (
    CloudCredentials,
    CloudSession,
    DeviceCloudError,
    RealDeviceCaps,
    build_capabilities,
    connect_real_device,
    fetch_session_info,
    load_credentials,
    session_summary_markdown,
    update_session_status,
)


class TestNormalisation(unittest.TestCase):

    def test_invalid_provider_raises(self):
        with self.assertRaises(DeviceCloudError):
            build_capabilities("aws", RealDeviceCaps("Pixel 7", "Android", "13"))


class TestLoadCredentials(unittest.TestCase):

    def test_browserstack_from_env(self):
        with patch.dict(os.environ, {
            "BROWSERSTACK_USERNAME": "u", "BROWSERSTACK_ACCESS_KEY": "k",
        }, clear=False):
            creds = load_credentials("browserstack")
            self.assertEqual(creds.username, "u")
            self.assertEqual(creds.access_key, "k")
            self.assertEqual(creds.redacted()["access_key"], "***")

    def test_missing_env_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(DeviceCloudError):
                load_credentials("saucelabs")


class TestBuildCapabilities(unittest.TestCase):

    def setUp(self):
        self.caps = RealDeviceCaps(
            device_name="iPhone 15",
            platform_name="iOS",
            platform_version="17",
            browser_name="Safari",
            build="b1",
            name="t1",
            project="webrunner",
        )

    def test_browserstack_shape(self):
        out = build_capabilities("browserstack", self.caps)
        self.assertEqual(out["browserName"], "Safari")
        self.assertEqual(out["bstack:options"]["deviceName"], "iPhone 15")
        self.assertEqual(out["bstack:options"]["osVersion"], "17")
        self.assertEqual(out["bstack:options"]["buildName"], "b1")

    def test_saucelabs_uses_appium_caps(self):
        out = build_capabilities("saucelabs", self.caps)
        self.assertEqual(out["appium:deviceName"], "iPhone 15")
        self.assertEqual(out["appium:platformVersion"], "17")
        self.assertEqual(out["appium:automationName"], "XCUITest")
        self.assertEqual(out["sauce:options"]["build"], "b1")

    def test_lambdatest_uses_lt_options(self):
        out = build_capabilities("lambdatest", self.caps)
        self.assertEqual(out["LT:Options"]["deviceName"], "iPhone 15")
        self.assertTrue(out["LT:Options"]["isRealMobile"])

    def test_android_uses_uiautomator(self):
        caps = RealDeviceCaps("Pixel 8", "Android", "14")
        out = build_capabilities("saucelabs", caps)
        self.assertEqual(out["appium:automationName"], "UiAutomator2")

    def test_extra_caps_merged(self):
        caps = RealDeviceCaps(
            "X", "Android", "12", extra={"acceptInsecureCerts": True},
        )
        out = build_capabilities("browserstack", caps)
        self.assertIs(out["acceptInsecureCerts"], True)


class TestConnectRealDevice(unittest.TestCase):

    def test_returns_driver_and_session(self):
        fake_driver = MagicMock(session_id="sess-123")
        connector = MagicMock(return_value=fake_driver)
        caps = RealDeviceCaps("Pixel 7", "Android", "13")
        creds = CloudCredentials("u", "k")
        driver, session = connect_real_device(
            "browserstack", caps,
            credentials=creds, retries=0, connector=connector,
        )
        self.assertIs(driver, fake_driver)
        self.assertEqual(session.session_id, "sess-123")
        self.assertIn("sess-123", session.dashboard_url)
        self.assertEqual(session.provider, "browserstack")
        connector.assert_called_once()

    def test_missing_session_id_raises(self):
        fake_driver = MagicMock(spec=[])  # no session_id attribute
        connector = MagicMock(return_value=fake_driver)
        caps = RealDeviceCaps("Pixel 7", "Android", "13")
        creds = CloudCredentials("u", "k")
        with self.assertRaises(DeviceCloudError):
            connect_real_device(
                "browserstack", caps,
                credentials=creds, retries=0, connector=connector,
            )

    def test_retries_then_succeeds(self):
        fake_driver = MagicMock(session_id="ok")
        connector = MagicMock(side_effect=[RuntimeError("boom"), fake_driver])
        caps = RealDeviceCaps("Pixel 7", "Android", "13")
        creds = CloudCredentials("u", "k")
        with patch("time.sleep"):
            _, session = connect_real_device(
                "saucelabs", caps,
                credentials=creds, retries=1, connector=connector,
            )
        self.assertEqual(session.session_id, "ok")
        self.assertEqual(connector.call_count, 2)

    def test_retries_exhausted_raises(self):
        connector = MagicMock(side_effect=RuntimeError("nope"))
        caps = RealDeviceCaps("Pixel 7", "Android", "13")
        creds = CloudCredentials("u", "k")
        with patch("time.sleep"):
            with self.assertRaises(DeviceCloudError):
                connect_real_device(
                    "lambdatest", caps,
                    credentials=creds, retries=2, connector=connector,
                )
        self.assertEqual(connector.call_count, 3)


class TestFetchSessionInfo(unittest.TestCase):

    def test_browserstack_extracts_video(self):
        creds = CloudCredentials("u", "k")
        request_fn = MagicMock(return_value={
            "automation_session": {
                "video_url": "https://video/x.mp4",
                "status": "passed",
            }
        })
        session = fetch_session_info(
            "browserstack", "sid", creds, request_fn=request_fn,
        )
        self.assertEqual(session.video_url, "https://video/x.mp4")
        self.assertEqual(session.status, "passed")
        request_fn.assert_called_once()

    def test_saucelabs_payload(self):
        creds = CloudCredentials("u", "k")
        request_fn = MagicMock(return_value={
            "video_url": "https://video/y.mp4", "status": "complete",
        })
        session = fetch_session_info(
            "saucelabs", "sid", creds, request_fn=request_fn,
        )
        self.assertEqual(session.video_url, "https://video/y.mp4")

    def test_unexpected_payload_raises(self):
        creds = CloudCredentials("u", "k")
        request_fn = MagicMock(return_value="not a dict")
        with self.assertRaises(DeviceCloudError):
            fetch_session_info(
                "lambdatest", "sid", creds, request_fn=request_fn,
            )


class TestUpdateSessionStatus(unittest.TestCase):

    def test_browserstack_put_status(self):
        creds = CloudCredentials("u", "k")
        request_fn = MagicMock(return_value={})
        update_session_status(
            "browserstack", "sid",
            passed=True, reason="all green",
            credentials=creds, request_fn=request_fn,
        )
        method, url, _creds_arg, payload = request_fn.call_args.args
        self.assertEqual(method, "PUT")
        self.assertIn("sid", url)
        self.assertEqual(payload, {"status": "passed", "reason": "all green"})

    def test_saucelabs_passed_flag(self):
        creds = CloudCredentials("u", "k")
        request_fn = MagicMock(return_value={})
        update_session_status(
            "saucelabs", "sid",
            passed=False, reason="boom",
            credentials=creds, request_fn=request_fn,
        )
        method, _url, _creds_arg, payload = request_fn.call_args.args
        self.assertEqual(method, "PUT")
        self.assertIs(payload["passed"], False)

    def test_lambdatest_uses_patch(self):
        creds = CloudCredentials("u", "k")
        request_fn = MagicMock(return_value={})
        update_session_status(
            "lambdatest", "sid",
            passed=True, credentials=creds, request_fn=request_fn,
        )
        method, _url, _creds_arg, payload = request_fn.call_args.args
        self.assertEqual(method, "PATCH")
        self.assertEqual(payload["status_ind"], "passed")


class TestRenderSummary(unittest.TestCase):

    def test_includes_dashboard_and_video(self):
        session = CloudSession(
            provider="browserstack",
            session_id="sid",
            dashboard_url="https://dash/sid",
            video_url="https://vid/sid.mp4",
            status="passed",
        )
        md = session_summary_markdown(session)
        self.assertIn("https://dash/sid", md)
        self.assertIn("https://vid/sid.mp4", md)
        self.assertIn("passed", md)


if __name__ == "__main__":
    unittest.main()
