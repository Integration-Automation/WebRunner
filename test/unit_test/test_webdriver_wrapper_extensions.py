"""
驗證 WebDriverWrapper 為支援 anti-bot / stealth / 進階情境新增的 API。
Tests for WebDriverWrapper APIs added for anti-bot / stealth / advanced scenarios.
"""
from __future__ import annotations

import base64
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.cdp.cdp_commands import CDPError
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.webdriver.webdriver_wrapper import (
    WebDriverWrapper,
    _options_dict,
    _webdriver_manager_dict,
)


class TestWebdriverManagerDict(unittest.TestCase):
    """Every manager entry must be callable with no args — the launch path does
    ``_webdriver_manager_dict.get(name)().install()``. A pre-built instance
    (not callable) silently broke chromium with a TypeError."""

    def test_all_entries_callable(self):
        for name, value in _webdriver_manager_dict.items():
            self.assertTrue(callable(value), f"{name} manager entry not callable")

    def test_chromium_resolves_to_manager(self):
        from webdriver_manager.chrome import ChromeDriverManager
        # Calling the entry (as the launch path does) must construct a manager,
        # not raise TypeError. ``.install()`` is intentionally not called here.
        self.assertIsInstance(_webdriver_manager_dict["chromium"](), ChromeDriverManager)

    def test_chromium_options_declare_browser_name(self):
        # chromium launches via webdriver.Chrome; its Options must declare
        # browserName, else webdriver.Chrome raises KeyError('browserName').
        self.assertIn("browserName", _options_dict["chromium"]().default_capabilities)
        self.assertIn("browserName", _options_dict["chrome"]().default_capabilities)


class TestQuit(unittest.TestCase):
    """``quit`` must quit the live driver, reset state, and no-op when idle."""

    def test_quit_calls_driver_and_resets_state(self):
        wrapper = WebDriverWrapper()
        driver = MagicMock(name="driver")
        wrapper.current_webdriver = driver
        wrapper._webdriver_name = "chrome"
        wrapper.quit()
        driver.quit.assert_called_once()
        self.assertIsNone(wrapper.current_webdriver)
        self.assertIsNone(wrapper._webdriver_name)

    def test_quit_no_driver_is_noop(self):
        wrapper = WebDriverWrapper()
        wrapper.current_webdriver = None
        wrapper.quit()  # must not raise
        self.assertIsNone(wrapper.current_webdriver)


class TestSetDriverExperimentalOptions(unittest.TestCase):
    """``set_driver`` 應將 experimental_options 透過 add_experimental_option 傳入 ChromeOptions。"""

    def _patched_set_driver(self, **set_driver_kwargs):
        """執行 set_driver 並回傳實際傳給 webdriver.Chrome 的 Options 物件。"""
        fake_options = MagicMock(name="ChromeOptions")
        # 由於 hasattr(driver_options, "add_experimental_option") 會被檢查，
        # MagicMock 預設會有任何屬性，因此天然滿足條件。
        fake_options_cls = MagicMock(return_value=fake_options)
        fake_driver_cls = MagicMock(name="ChromeDriverClass")
        fake_manager_cls = MagicMock(name="ChromeDriverManager")

        with patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._options_dict",
            {"chrome": fake_options_cls},
            clear=False,
        ), patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_dict",
            {"chrome": fake_driver_cls},
            clear=False,
        ), patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_manager_dict",
            {"chrome": fake_manager_cls},
            clear=False,
        ):
            wrapper = WebDriverWrapper()
            wrapper.set_driver("chrome", **set_driver_kwargs)
        return fake_options, fake_driver_cls

    def test_experimental_options_forwarded(self):
        exp = {
            "excludeSwitches": ["enable-automation"],
            "useAutomationExtension": False,
        }
        fake_options, fake_driver_cls = self._patched_set_driver(
            options=["--start-maximized"],
            experimental_options=exp,
        )
        fake_options.add_argument.assert_called_once_with(argument="--start-maximized")
        fake_options.add_experimental_option.assert_any_call(
            "excludeSwitches", ["enable-automation"]
        )
        fake_options.add_experimental_option.assert_any_call(
            "useAutomationExtension", False
        )
        # 確認 Options 物件最終被傳給 webdriver.Chrome
        fake_driver_cls.assert_called_once()
        _, kwargs = fake_driver_cls.call_args
        self.assertIs(kwargs.get("options"), fake_options)

    def test_experimental_options_without_args_still_builds_options(self):
        fake_options, fake_driver_cls = self._patched_set_driver(
            experimental_options={"prefs": {"download.default_directory": "/opt/dl"}},
        )
        fake_options.add_argument.assert_not_called()
        fake_options.add_experimental_option.assert_called_once_with(
            "prefs", {"download.default_directory": "/opt/dl"}
        )
        _, kwargs = fake_driver_cls.call_args
        self.assertIs(kwargs.get("options"), fake_options)

    def test_unsupported_browser_raises(self):
        # FirefoxOptions 不支援 add_experimental_option。
        class FakeFirefoxOptions:
            def add_argument(self, argument):  # noqa: D401 — fake
                pass
            # 故意沒有 add_experimental_option

        fake_options_cls = MagicMock(return_value=FakeFirefoxOptions())
        fake_driver_cls = MagicMock(name="FirefoxDriverClass")
        fake_manager_cls = MagicMock(name="FirefoxDriverManager")

        with patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._options_dict",
            {"firefox": fake_options_cls},
            clear=False,
        ), patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_dict",
            {"firefox": fake_driver_cls},
            clear=False,
        ), patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_manager_dict",
            {"firefox": fake_manager_cls},
            clear=False,
        ):
            wrapper = WebDriverWrapper()
            with self.assertRaises(WebRunnerException):
                wrapper.set_driver(
                    "firefox",
                    experimental_options={"excludeSwitches": ["enable-automation"]},
                )


class TestExecuteCdpCmd(unittest.TestCase):

    def test_dispatches_to_selenium_cdp(self):
        wrapper = WebDriverWrapper()
        fake_driver = MagicMock()
        fake_driver.execute_cdp_cmd.return_value = {"identifier": "abc123"}
        wrapper.current_webdriver = fake_driver

        result = wrapper.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "console.log('hi');"},
        )
        self.assertEqual(result, {"identifier": "abc123"})
        fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "console.log('hi');"},
        )

    def test_empty_args_default_to_dict(self):
        wrapper = WebDriverWrapper()
        fake_driver = MagicMock()
        fake_driver.execute_cdp_cmd.return_value = None
        wrapper.current_webdriver = fake_driver

        wrapper.execute_cdp_cmd("Network.enable")
        fake_driver.execute_cdp_cmd.assert_called_once_with("Network.enable", {})

    def test_no_driver_raises(self):
        wrapper = WebDriverWrapper()
        wrapper.current_webdriver = None
        with self.assertRaises(CDPError):
            wrapper.execute_cdp_cmd("Network.enable")

    def test_non_chromium_driver_raises(self):
        wrapper = WebDriverWrapper()
        # object() 沒有 execute_cdp_cmd 屬性，模擬 Firefox / Safari driver。
        wrapper.current_webdriver = object()
        with self.assertRaises(CDPError):
            wrapper.execute_cdp_cmd("Network.enable")


class TestSaveScreenshot(unittest.TestCase):

    def test_delegates_to_driver(self):
        wrapper = WebDriverWrapper()
        fake_driver = MagicMock()
        fake_driver.save_screenshot.return_value = True
        wrapper.current_webdriver = fake_driver

        self.assertTrue(wrapper.save_screenshot("/opt/out.png"))
        fake_driver.save_screenshot.assert_called_once_with("/opt/out.png")

    def test_returns_false_on_exception(self):
        wrapper = WebDriverWrapper()
        fake_driver = MagicMock()
        fake_driver.save_screenshot.side_effect = RuntimeError("disk full")
        wrapper.current_webdriver = fake_driver

        self.assertFalse(wrapper.save_screenshot("/opt/out.png"))


# --- Group A: page / window metadata --------------------------------------

class TestPageWindowMetadata(unittest.TestCase):

    def setUp(self):
        self.wrapper = WebDriverWrapper()
        self.fake_driver = MagicMock()
        self.wrapper.current_webdriver = self.fake_driver

    def test_get_current_url(self):
        self.fake_driver.current_url = "https://example.com/"
        self.assertEqual(self.wrapper.get_current_url(), "https://example.com/")

    def test_get_title(self):
        self.fake_driver.title = "Example Domain"
        self.assertEqual(self.wrapper.get_title(), "Example Domain")

    def test_get_page_source(self):
        self.fake_driver.page_source = "<html></html>"
        self.assertEqual(self.wrapper.get_page_source(), "<html></html>")

    def test_get_window_handles(self):
        self.fake_driver.window_handles = ["w1", "w2"]
        self.assertEqual(self.wrapper.get_window_handles(), ["w1", "w2"])

    def test_get_current_window_handle(self):
        self.fake_driver.current_window_handle = "w1"
        self.assertEqual(self.wrapper.get_current_window_handle(), "w1")

    def test_new_window_default_tab(self):
        self.wrapper.new_window()
        self.fake_driver.switch_to.new_window.assert_called_once_with("tab")

    def test_new_window_explicit_window(self):
        self.wrapper.new_window("window")
        self.fake_driver.switch_to.new_window.assert_called_once_with("window")

    def test_close_window(self):
        self.wrapper.close_window()
        self.fake_driver.close.assert_called_once()

    def test_getters_return_none_on_exception(self):
        # 模擬 driver 拋例外的情況：所有 getter 應回 None 而非崩潰
        broken_driver = MagicMock()
        type(broken_driver).current_url = unittest.mock.PropertyMock(
            side_effect=RuntimeError("no session")
        )
        self.wrapper.current_webdriver = broken_driver
        self.assertIsNone(self.wrapper.get_current_url())


# --- Group B: add_extension + attach_to_existing_browser ------------------

class TestExtensionsAndAttach(unittest.TestCase):

    def _patched_chrome(self, fake_options):
        fake_options_cls = MagicMock(return_value=fake_options)
        fake_driver_cls = MagicMock(name="ChromeDriverClass")
        fake_manager_cls = MagicMock(name="ChromeDriverManager")
        return patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._options_dict",
            {"chrome": fake_options_cls},
            clear=False,
        ), patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_dict",
            {"chrome": fake_driver_cls},
            clear=False,
        ), patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_manager_dict",
            {"chrome": fake_manager_cls},
            clear=False,
        ), fake_driver_cls

    def test_extension_paths_forwarded(self):
        fake_options = MagicMock(name="ChromeOptions")
        p1, p2, p3, fake_driver_cls = self._patched_chrome(fake_options)
        with p1, p2, p3:
            wrapper = WebDriverWrapper()
            wrapper.set_driver(
                "chrome",
                extension_paths=["/opt/a.crx", "/opt/b.crx"],
            )
        fake_options.add_extension.assert_any_call("/opt/a.crx")
        fake_options.add_extension.assert_any_call("/opt/b.crx")
        _, kwargs = fake_driver_cls.call_args
        self.assertIs(kwargs.get("options"), fake_options)

    def test_extension_unsupported_browser_raises(self):
        class FakeIeOptions:
            def add_argument(self, argument):  # noqa: D401
                pass
            # 故意沒有 add_extension

        fake_options_cls = MagicMock(return_value=FakeIeOptions())
        fake_driver_cls = MagicMock(name="IeDriverClass")
        fake_manager_cls = MagicMock(name="IeDriverManager")
        with patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._options_dict",
            {"ie": fake_options_cls},
            clear=False,
        ), patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_dict",
            {"ie": fake_driver_cls},
            clear=False,
        ), patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_manager_dict",
            {"ie": fake_manager_cls},
            clear=False,
        ):
            wrapper = WebDriverWrapper()
            with self.assertRaises(WebRunnerException):
                wrapper.set_driver("ie", extension_paths=["/opt/a.crx"])

    def test_browser_without_manager_skips_install(self):
        # Safari (and any browser with no webdriver-manager entry) must launch
        # without crashing at the install step — there is no None() to call.
        fake_driver = MagicMock(name="SafariDriver")
        fake_driver_cls = MagicMock(name="SafariDriverClass", return_value=fake_driver)
        with patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_dict",
            {"safari": fake_driver_cls},
            clear=False,
        ):
            wrapper = WebDriverWrapper()
            result = wrapper.set_driver("safari")
        self.assertIs(result, fake_driver)
        fake_driver_cls.assert_called_once()

    def test_attach_to_existing_browser_merges_debugger_address(self):
        wrapper = WebDriverWrapper()
        with patch.object(wrapper, "set_driver", return_value=MagicMock()) as set_drv:
            wrapper.attach_to_existing_browser(
                "127.0.0.1:9222",
                experimental_options={"detach": True},
            )
        set_drv.assert_called_once()
        args, kwargs = set_drv.call_args
        self.assertEqual(args[0], "chrome")
        merged = kwargs["experimental_options"]
        self.assertEqual(merged["debuggerAddress"], "127.0.0.1:9222")
        self.assertTrue(merged["detach"])


# --- Group C: CDP convenience methods -------------------------------------

class TestCdpConvenience(unittest.TestCase):

    def setUp(self):
        self.wrapper = WebDriverWrapper()
        self.fake_driver = MagicMock()
        self.wrapper.current_webdriver = self.fake_driver

    def test_add_script_to_evaluate_on_new_document(self):
        self.fake_driver.execute_cdp_cmd.return_value = {"identifier": "1"}
        ident = self.wrapper.add_script_to_evaluate_on_new_document(
            "console.log('hi');"
        )
        self.assertEqual(ident, "1")
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "console.log('hi');"},
        )

    def test_set_user_agent(self):
        self.wrapper.set_user_agent("Mozilla/5.0 (Custom)")
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Network.setUserAgentOverride",
            {"userAgent": "Mozilla/5.0 (Custom)"},
        )

    def test_set_extra_http_headers(self):
        self.wrapper.set_extra_http_headers({"X-Test": "1"})
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Network.setExtraHTTPHeaders",
            {"headers": {"X-Test": "1"}},
        )

    def test_set_geolocation_defaults(self):
        self.wrapper.set_geolocation(25.03, 121.56)
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Emulation.setGeolocationOverride",
            {"latitude": 25.03, "longitude": 121.56, "accuracy": 100},
        )


# --- Group D: print_page + full-page screenshot ---------------------------

class TestPrintAndFullPageScreenshot(unittest.TestCase):

    def setUp(self):
        self.wrapper = WebDriverWrapper()
        self.fake_driver = MagicMock()
        self.wrapper.current_webdriver = self.fake_driver

    def test_save_full_page_screenshot_writes_decoded_png(self):
        png_bytes = b"\x89PNG\r\n\x1a\nFAKE"
        self.fake_driver.execute_cdp_cmd.return_value = {
            "data": base64.b64encode(png_bytes).decode("ascii"),
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "shot.png")
            self.assertTrue(self.wrapper.save_full_page_screenshot(target))
            with open(target, "rb") as fh:
                self.assertEqual(fh.read(), png_bytes)
        # 驗證確實呼叫 CDP 並帶 captureBeyondViewport
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": True, "fromSurface": True},
        )

    def test_save_full_page_screenshot_returns_false_on_empty_data(self):
        self.fake_driver.execute_cdp_cmd.return_value = {"data": ""}
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "shot.png")
            self.assertFalse(self.wrapper.save_full_page_screenshot(target))
            self.assertFalse(os.path.exists(target))

    def test_print_page_writes_decoded_pdf(self):
        pdf_bytes = b"%PDF-1.4\nfake"
        self.fake_driver.print_page.return_value = base64.b64encode(pdf_bytes).decode("ascii")
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "out.pdf")
            self.assertTrue(self.wrapper.print_page(target))
            with open(target, "rb") as fh:
                self.assertEqual(fh.read(), pdf_bytes)
        self.fake_driver.print_page.assert_called_once_with()

    def test_print_page_with_options(self):
        sentinel_options = object()
        self.fake_driver.print_page.return_value = base64.b64encode(b"%PDF-").decode("ascii")
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "out.pdf")
            self.wrapper.print_page(target, print_options=sentinel_options)
        self.fake_driver.print_page.assert_called_once_with(sentinel_options)

    def test_print_page_returns_false_on_exception(self):
        self.fake_driver.print_page.side_effect = RuntimeError("boom")
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "out.pdf")
            self.assertFalse(self.wrapper.print_page(target))


# --- Group E: CDP emulation overrides -------------------------------------

class TestEmulationOverrides(unittest.TestCase):

    def setUp(self):
        self.wrapper = WebDriverWrapper()
        self.fake_driver = MagicMock()
        self.wrapper.current_webdriver = self.fake_driver

    def test_set_timezone(self):
        self.wrapper.set_timezone("Asia/Tokyo")
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Emulation.setTimezoneOverride", {"timezoneId": "Asia/Tokyo"}
        )

    def test_set_locale(self):
        self.wrapper.set_locale("ja-JP")
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Emulation.setLocaleOverride", {"locale": "ja-JP"}
        )

    def test_set_device_metrics(self):
        self.wrapper.set_device_metrics(390, 844, device_scale_factor=3, mobile=True)
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 3, "mobile": True},
        )

    def test_clear_device_metrics(self):
        self.wrapper.clear_device_metrics()
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Emulation.clearDeviceMetricsOverride", {}
        )

    def test_clear_geolocation_override(self):
        self.wrapper.clear_geolocation_override()
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Emulation.clearGeolocationOverride", {}
        )

    def test_set_network_conditions_offline(self):
        self.wrapper.set_network_conditions(offline=True)
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Network.emulateNetworkConditions",
            {
                "offline": True,
                "latency": 0,
                "downloadThroughput": -1,
                "uploadThroughput": -1,
            },
        )

    def test_set_network_conditions_throttled(self):
        self.wrapper.set_network_conditions(
            offline=False, latency=200, download_throughput=50_000, upload_throughput=10_000
        )
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": 200,
                "downloadThroughput": 50_000,
                "uploadThroughput": 10_000,
            },
        )


# --- Group F: cookie persistence + origin storage -------------------------

class TestCookiePersistence(unittest.TestCase):

    def setUp(self):
        self.wrapper = WebDriverWrapper()
        self.fake_driver = MagicMock()
        self.wrapper.current_webdriver = self.fake_driver

    def test_save_and_load_roundtrip(self):
        cookies = [
            {"name": "session", "value": "abc", "domain": "example.com"},
            {"name": "lang", "value": "en", "domain": "example.com"},
        ]
        self.fake_driver.get_cookies.return_value = cookies
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cookies.json")
            self.assertTrue(self.wrapper.save_cookies(path))

            # 載回時清掉 mock 並驗證 add_cookie 被逐筆呼叫
            self.fake_driver.add_cookie.reset_mock()
            added = self.wrapper.load_cookies(path)
            self.assertEqual(added, 2)
            self.assertEqual(self.fake_driver.add_cookie.call_count, 2)
            self.fake_driver.add_cookie.assert_any_call(cookies[0])
            self.fake_driver.add_cookie.assert_any_call(cookies[1])

    def test_load_cookies_skips_failing_entries(self):
        import json as _json
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cookies.json")
            with open(path, "w", encoding="utf-8") as fh:
                _json.dump(
                    [
                        {"name": "ok", "value": "1", "domain": "example.com"},
                        {"name": "bad", "value": "2", "domain": "wrong.example.com"},
                    ],
                    fh,
                )
            # 第一個成功，第二個 raise
            self.fake_driver.add_cookie.side_effect = [None, RuntimeError("domain mismatch")]
            added = self.wrapper.load_cookies(path)
            self.assertEqual(added, 1)

    def test_save_cookies_returns_false_on_exception(self):
        self.fake_driver.get_cookies.side_effect = RuntimeError("no driver")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "cookies.json")
            self.assertFalse(self.wrapper.save_cookies(path))

    def test_clear_origin_storage(self):
        self.wrapper.clear_origin_storage("https://example.com")
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Storage.clearDataForOrigin",
            {"origin": "https://example.com", "storageTypes": "all"},
        )


# --- Group G: network blocking / cache ------------------------------------

class TestNetworkBlocking(unittest.TestCase):

    def setUp(self):
        self.wrapper = WebDriverWrapper()
        self.fake_driver = MagicMock()
        self.wrapper.current_webdriver = self.fake_driver

    def test_block_urls(self):
        self.wrapper.block_urls(["*.doubleclick.net/*", "*.googletagmanager.com/*"])
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Network.setBlockedURLs",
            {"urls": ["*.doubleclick.net/*", "*.googletagmanager.com/*"]},
        )

    def test_unblock_urls(self):
        self.wrapper.unblock_urls()
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Network.setBlockedURLs", {"urls": []}
        )

    def test_set_cache_disabled_true(self):
        self.wrapper.set_cache_disabled(True)
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Network.setCacheDisabled", {"cacheDisabled": True}
        )

    def test_set_cache_disabled_default_true(self):
        self.wrapper.set_cache_disabled()
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Network.setCacheDisabled", {"cacheDisabled": True}
        )


# --- Group H: download directory ------------------------------------------

class TestDownloadDirectory(unittest.TestCase):

    def test_set_download_directory(self):
        wrapper = WebDriverWrapper()
        fake_driver = MagicMock()
        wrapper.current_webdriver = fake_driver
        wrapper.set_download_directory("/opt/downloads")
        fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Browser.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": "/opt/downloads"},
        )

    def test_set_download_directory_deny(self):
        wrapper = WebDriverWrapper()
        fake_driver = MagicMock()
        wrapper.current_webdriver = fake_driver
        wrapper.set_download_directory("/opt/downloads", behavior="deny")
        fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Browser.setDownloadBehavior",
            {"behavior": "deny", "downloadPath": "/opt/downloads"},
        )


# --- Group I: page convenience --------------------------------------------

class TestPageConvenience(unittest.TestCase):

    def setUp(self):
        self.wrapper = WebDriverWrapper()
        self.fake_driver = MagicMock()
        self.wrapper.current_webdriver = self.fake_driver

    def test_reload_with_cache(self):
        self.wrapper.reload(ignore_cache=False)
        self.fake_driver.refresh.assert_called_once()
        self.fake_driver.execute_cdp_cmd.assert_not_called()

    def test_reload_ignore_cache(self):
        self.wrapper.reload(ignore_cache=True)
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Page.reload", {"ignoreCache": True}
        )
        self.fake_driver.refresh.assert_not_called()

    def test_scroll_to_element(self):
        element = MagicMock(name="element")
        self.wrapper.scroll_to_element(element)
        args, _ = self.fake_driver.execute_script.call_args
        self.assertIn("scrollIntoView", args[0])
        self.assertIs(args[1], element)

    def test_scroll_to_top(self):
        self.wrapper.scroll_to_top()
        self.fake_driver.execute_script.assert_called_once_with("window.scrollTo(0, 0);")

    def test_scroll_to_bottom(self):
        self.wrapper.scroll_to_bottom()
        self.fake_driver.execute_script.assert_called_once_with(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

    def test_bring_to_front(self):
        self.wrapper.bring_to_front()
        self.fake_driver.execute_cdp_cmd.assert_called_once_with("Page.bringToFront", {})

    def _setup_two_windows(self, urls=("https://a.com/", "https://b.com/"), titles=("Alpha", "Beta")):
        self.fake_driver.current_window_handle = "w1"
        self.fake_driver.window_handles = ["w1", "w2"]
        # 切換到不同 handle 時，current_url / title 取對應值
        urls_iter = iter(urls)
        titles_iter = iter(titles)

        def _switch_window(handle):
            # 模擬切窗：每次切窗後 current_url / title 換成下一筆
            type(self.fake_driver).current_url = unittest.mock.PropertyMock(
                return_value=next(urls_iter, urls[-1])
            )
            type(self.fake_driver).title = unittest.mock.PropertyMock(
                return_value=next(titles_iter, titles[-1])
            )

        self.fake_driver.switch_to.window.side_effect = _switch_window

    def test_switch_to_window_by_url_matches_second(self):
        self._setup_two_windows(urls=("https://a.com/", "https://target.com/page"))
        self.assertTrue(self.wrapper.switch_to_window_by_url("target"))
        # switch_to.window 應被呼叫到第二個 handle 為止
        called_handles = [c.args[0] for c in self.fake_driver.switch_to.window.call_args_list]
        self.assertEqual(called_handles[:2], ["w1", "w2"])

    def test_switch_to_window_by_url_no_match_restores_original(self):
        self._setup_two_windows(urls=("https://a.com/", "https://b.com/"))
        self.assertFalse(self.wrapper.switch_to_window_by_url("not-present"))
        # 最後一次切窗應該是切回原視窗 "w1"
        last_handle = self.fake_driver.switch_to.window.call_args_list[-1].args[0]
        self.assertEqual(last_handle, "w1")

    def test_switch_to_window_by_title_matches(self):
        self._setup_two_windows(titles=("Alpha", "Beta Target"))
        self.assertTrue(self.wrapper.switch_to_window_by_title("Target"))


# --- Group J: BiDi event listeners ----------------------------------------

class TestBidiListeners(unittest.TestCase):

    def setUp(self):
        self.wrapper = WebDriverWrapper()
        self.fake_driver = MagicMock()
        self.fake_script = MagicMock()
        self.fake_driver.script = self.fake_script
        self.wrapper.current_webdriver = self.fake_driver

    def test_add_console_listener_returns_subscription_id(self):
        self.fake_script.add_console_message_handler.return_value = 42
        cb = lambda msg: None  # noqa: E731
        self.assertEqual(self.wrapper.add_console_listener(cb), 42)
        self.fake_script.add_console_message_handler.assert_called_once_with(cb)

    def test_add_js_error_listener_returns_subscription_id(self):
        self.fake_script.add_javascript_error_handler.return_value = 7
        cb = lambda err: None  # noqa: E731
        self.assertEqual(self.wrapper.add_js_error_listener(cb), 7)
        self.fake_script.add_javascript_error_handler.assert_called_once_with(cb)

    def test_remove_console_listener_success(self):
        self.assertTrue(self.wrapper.remove_console_listener(42))
        self.fake_script.remove_console_message_handler.assert_called_once_with(42)

    def test_remove_js_error_listener_success(self):
        self.assertTrue(self.wrapper.remove_js_error_listener(7))
        self.fake_script.remove_javascript_error_handler.assert_called_once_with(7)

    def test_remove_returns_false_when_underlying_fails(self):
        self.fake_script.remove_console_message_handler.side_effect = RuntimeError("gone")
        self.assertFalse(self.wrapper.remove_console_listener(42))

    def test_listener_raises_without_bidi_support(self):
        # Driver 沒有 script 屬性，模擬 Selenium < 4.16 或未啟用 BiDi
        driver_without_bidi = MagicMock(spec=["execute"])
        self.wrapper.current_webdriver = driver_without_bidi
        with self.assertRaises(WebRunnerException):
            self.wrapper.add_console_listener(lambda m: None)


class TestSetDriverEnableBidi(unittest.TestCase):

    def test_enable_bidi_sets_capability(self):
        fake_options = MagicMock(name="ChromeOptions")
        fake_options_cls = MagicMock(return_value=fake_options)
        fake_driver_cls = MagicMock(name="ChromeDriverClass")
        fake_manager_cls = MagicMock(name="ChromeDriverManager")
        with patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._options_dict",
            {"chrome": fake_options_cls},
            clear=False,
        ), patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_dict",
            {"chrome": fake_driver_cls},
            clear=False,
        ), patch.dict(
            "je_web_runner.webdriver.webdriver_wrapper._webdriver_manager_dict",
            {"chrome": fake_manager_cls},
            clear=False,
        ):
            wrapper = WebDriverWrapper()
            wrapper.set_driver("chrome", enable_bidi=True)
        fake_options.set_capability.assert_called_once_with("webSocketUrl", True)


# --- Group K: Fetch interception primitives -------------------------------

class TestFetchInterception(unittest.TestCase):

    def setUp(self):
        self.wrapper = WebDriverWrapper()
        self.fake_driver = MagicMock()
        self.wrapper.current_webdriver = self.fake_driver

    def test_enable_default_intercepts_everything(self):
        self.wrapper.enable_fetch_interception()
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Fetch.enable",
            {"patterns": [{"urlPattern": "*"}], "handleAuthRequests": False},
        )

    def test_enable_with_string_patterns(self):
        self.wrapper.enable_fetch_interception(
            patterns=["*.doubleclick.net/*", "https://api.example.com/*"],
            handle_auth=True,
        )
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Fetch.enable",
            {
                "patterns": [
                    {"urlPattern": "*.doubleclick.net/*"},
                    {"urlPattern": "https://api.example.com/*"},
                ],
                "handleAuthRequests": True,
            },
        )

    def test_enable_with_dict_patterns_passes_through(self):
        rp = {"urlPattern": "*/api/*", "resourceType": "XHR", "requestStage": "Response"}
        self.wrapper.enable_fetch_interception(patterns=[rp])
        args, _ = self.fake_driver.execute_cdp_cmd.call_args
        self.assertEqual(args[1]["patterns"], [rp])

    def test_enable_rejects_bad_pattern_type(self):
        with self.assertRaises(WebRunnerException):
            self.wrapper.enable_fetch_interception(patterns=[123])

    def test_disable(self):
        self.wrapper.disable_fetch_interception()
        self.fake_driver.execute_cdp_cmd.assert_called_once_with("Fetch.disable", {})

    def test_continue_request_minimal(self):
        self.wrapper.continue_request("req-123")
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Fetch.continueRequest", {"requestId": "req-123"}
        )

    def test_continue_request_with_overrides(self):
        self.wrapper.continue_request(
            "req-123",
            url="https://override.example.com/",
            method="POST",
            post_data="hello",
            headers={"X-Test": "1", "X-Two": 2},
        )
        args = self.fake_driver.execute_cdp_cmd.call_args.args
        self.assertEqual(args[0], "Fetch.continueRequest")
        params = args[1]
        self.assertEqual(params["url"], "https://override.example.com/")
        self.assertEqual(params["method"], "POST")
        self.assertEqual(
            base64.b64decode(params["postData"]).decode("utf-8"), "hello"
        )
        self.assertEqual(
            params["headers"],
            [{"name": "X-Test", "value": "1"}, {"name": "X-Two", "value": "2"}],
        )

    def test_continue_request_post_data_bytes_passthrough(self):
        self.wrapper.continue_request("req-1", post_data=b"\x00\x01raw")
        params = self.fake_driver.execute_cdp_cmd.call_args.args[1]
        self.assertEqual(base64.b64decode(params["postData"]), b"\x00\x01raw")

    def test_fulfill_request_full(self):
        self.wrapper.fulfill_request(
            "req-1",
            response_code=200,
            body="hello world",
            response_headers={"Content-Type": "text/plain"},
            response_phrase="OK",
        )
        args = self.fake_driver.execute_cdp_cmd.call_args.args
        self.assertEqual(args[0], "Fetch.fulfillRequest")
        params = args[1]
        self.assertEqual(params["requestId"], "req-1")
        self.assertEqual(params["responseCode"], 200)
        self.assertEqual(
            params["responseHeaders"],
            [{"name": "Content-Type", "value": "text/plain"}],
        )
        self.assertEqual(
            base64.b64decode(params["body"]).decode("utf-8"), "hello world"
        )
        self.assertEqual(params["responsePhrase"], "OK")

    def test_fulfill_request_minimal(self):
        self.wrapper.fulfill_request("req-2", response_code=204)
        params = self.fake_driver.execute_cdp_cmd.call_args.args[1]
        self.assertEqual(params, {"requestId": "req-2", "responseCode": 204})

    def test_fail_request_default(self):
        self.wrapper.fail_request("req-9")
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Fetch.failRequest",
            {"requestId": "req-9", "errorReason": "Aborted"},
        )

    def test_fail_request_explicit_reason(self):
        self.wrapper.fail_request("req-10", error_reason="AccessDenied")
        self.fake_driver.execute_cdp_cmd.assert_called_once_with(
            "Fetch.failRequest",
            {"requestId": "req-10", "errorReason": "AccessDenied"},
        )


if __name__ == "__main__":
    unittest.main()
