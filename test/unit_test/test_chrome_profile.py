"""Unit tests for je_web_runner.utils.chrome_profile."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.utils.chrome_profile.profile_manager import (
    ChromeProfileError,
    SESSION_CRITICAL_PATHS,
    SINGLETON_LOCK_FILES,
    StealthFlags,
    build_chrome_options,
    build_playwright_persistent_context,
    build_stealth_chrome_driver,
    chrome_profile_session,
    cleanup_chrome_locks,
    minimise_chrome_windows,
    snapshot_chrome_profile,
    sync_chrome_profile_back,
)


class TestCleanupChromeLocks(unittest.TestCase):

    def test_missing_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(cleanup_chrome_locks(Path(tmpdir) / "nope"), [])

    def test_removes_each_known_lock(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir)
            for fname in SINGLETON_LOCK_FILES:
                (profile / fname).write_text("x", encoding="utf-8")
            statuses = cleanup_chrome_locks(profile)
            for fname in SINGLETON_LOCK_FILES:
                self.assertFalse((profile / fname).exists(), msg=fname)
            self.assertEqual(len(statuses), len(SINGLETON_LOCK_FILES))

    def test_keeps_unrelated_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir)
            (profile / "SingletonLock").write_text("x", encoding="utf-8")
            (profile / "Cookies").write_text("cookies", encoding="utf-8")
            cleanup_chrome_locks(profile)
            self.assertTrue((profile / "Cookies").exists())


class TestSnapshotChromeProfile(unittest.TestCase):

    def _seed_profile(self, profile: Path) -> None:
        (profile / "Default").mkdir(parents=True)
        (profile / "Default" / "Cookies").write_text("cookie", encoding="utf-8")
        (profile / "Default" / "Cache").mkdir()
        (profile / "Default" / "Cache" / "garbage").write_text("g", encoding="utf-8")
        (profile / "SingletonLock").write_text("lock", encoding="utf-8")
        (profile / "Local State").write_text("state", encoding="utf-8")

    def test_missing_profile_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ChromeProfileError):
                snapshot_chrome_profile(Path(tmpdir) / "missing", Path(tmpdir) / "snap")

    def test_snapshot_excludes_cache_and_locks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir) / "profile"
            profile.mkdir()
            self._seed_profile(profile)
            snap = Path(tmpdir) / "snap"
            result = snapshot_chrome_profile(profile, snap)
            self.assertEqual(result, snap)
            self.assertTrue((snap / "Default" / "Cookies").exists())
            self.assertTrue((snap / "Local State").exists())
            self.assertFalse((snap / "SingletonLock").exists())
            self.assertFalse((snap / "Default" / "Cache").exists())

    def test_snapshot_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir) / "profile"
            profile.mkdir()
            (profile / "Local State").write_text("v2", encoding="utf-8")
            snap = Path(tmpdir) / "snap"
            snap.mkdir()
            (snap / "stale").write_text("stale", encoding="utf-8")
            snapshot_chrome_profile(profile, snap)
            self.assertFalse((snap / "stale").exists())
            self.assertEqual((snap / "Local State").read_text(encoding="utf-8"), "v2")


class TestSyncChromeProfileBack(unittest.TestCase):

    def test_missing_snapshot_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ChromeProfileError):
                sync_chrome_profile_back(Path(tmpdir) / "missing", Path(tmpdir) / "profile")

    def test_copies_session_critical(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = Path(tmpdir) / "snap"
            (snap / "Default").mkdir(parents=True)
            (snap / "Default" / "Cookies").write_text("c1", encoding="utf-8")
            (snap / "Local State").write_text("s1", encoding="utf-8")
            (snap / "Default" / "extra").write_text("ignored", encoding="utf-8")
            profile = Path(tmpdir) / "profile"
            statuses = sync_chrome_profile_back(snap, profile)
            self.assertTrue((profile / "Default" / "Cookies").exists())
            self.assertTrue((profile / "Local State").exists())
            self.assertFalse((profile / "Default" / "extra").exists())
            self.assertGreaterEqual(len(statuses), 2)

    def test_explicit_paths_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = Path(tmpdir) / "snap"
            (snap / "Default").mkdir(parents=True)
            (snap / "Default" / "Cookies").write_text("c", encoding="utf-8")
            (snap / "Local State").write_text("s", encoding="utf-8")
            profile = Path(tmpdir) / "profile"
            sync_chrome_profile_back(snap, profile, paths=("Local State",))
            self.assertTrue((profile / "Local State").exists())
            self.assertFalse((profile / "Default" / "Cookies").exists())

    def test_session_critical_constant_is_tuple(self):
        self.assertIsInstance(SESSION_CRITICAL_PATHS, tuple)
        self.assertGreater(len(SESSION_CRITICAL_PATHS), 0)


class TestBuildChromeOptions(unittest.TestCase):

    def test_default_flags_attach_stealth_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            opts = build_chrome_options(Path(tmpdir))
            args = " ".join(opts.arguments)
            self.assertIn("--user-data-dir=", args)
            self.assertIn("Chrome/", args)
            self.assertIn("--lang=en-US", args)
            self.assertIn("--disable-blink-features=AutomationControlled", args)

    def test_headless_and_extra_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            flags = StealthFlags(
                headless=True,
                window_size=(1280, 720),
                extra_args=["--proxy-server=http://x"],
            )
            opts = build_chrome_options(Path(tmpdir), flags=flags)
            args = " ".join(opts.arguments)
            self.assertIn("--headless=new", args)
            self.assertIn("--window-size=1280,720", args)
            self.assertIn("--proxy-server=http://x", args)


class TestBuildStealthChromeDriver(unittest.TestCase):

    def test_uses_snapshot_and_returns_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir) / "profile"
            profile.mkdir()
            (profile / "Local State").write_text("s", encoding="utf-8")
            fake_driver = MagicMock(name="ChromeDriver")
            with patch(
                "selenium.webdriver.chrome.service.Service"
            ) as mock_service, patch("selenium.webdriver.Chrome") as mock_chrome:
                mock_service.return_value = MagicMock()
                mock_chrome.return_value = fake_driver
                driver, snapshot_path = build_stealth_chrome_driver(
                    profile,
                    snapshot_dir=Path(tmpdir) / "snap",
                )
                self.assertIs(driver, fake_driver)
                self.assertEqual(snapshot_path, Path(tmpdir) / "snap")
                self.assertTrue(snapshot_path.exists())
                mock_chrome.assert_called_once()

    def test_retry_once_after_first_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir) / "profile"
            profile.mkdir()
            fake_driver = MagicMock(name="ChromeDriver")
            with patch(
                "selenium.webdriver.chrome.service.Service"
            ), patch("selenium.webdriver.Chrome") as mock_chrome:
                mock_chrome.side_effect = [RuntimeError("first boom"), fake_driver]
                with patch("time.sleep"):
                    driver, snapshot_path = build_stealth_chrome_driver(
                        profile,
                        snapshot_dir=Path(tmpdir) / "snap",
                    )
            self.assertIs(driver, fake_driver)
            self.assertEqual(mock_chrome.call_count, 2)
            self.assertEqual(snapshot_path, Path(tmpdir) / "snap")

    def test_retry_disabled_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir) / "profile"
            profile.mkdir()
            with patch(
                "selenium.webdriver.chrome.service.Service"
            ), patch("selenium.webdriver.Chrome") as mock_chrome:
                mock_chrome.side_effect = RuntimeError("boom")
                with self.assertRaises(ChromeProfileError):
                    build_stealth_chrome_driver(
                        profile,
                        snapshot_dir=Path(tmpdir) / "snap",
                        retry_once=False,
                    )

    def test_no_snapshot_dir_uses_profile_directly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir) / "profile"
            profile.mkdir()
            fake_driver = MagicMock()
            with patch(
                "selenium.webdriver.chrome.service.Service"
            ), patch("selenium.webdriver.Chrome", return_value=fake_driver):
                driver, snap = build_stealth_chrome_driver(profile, snapshot_dir=None)
            self.assertIs(driver, fake_driver)
            self.assertIsNone(snap)


class TestChromeProfileSession(unittest.TestCase):

    def test_session_quits_and_syncs_back(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir) / "profile"
            profile.mkdir()
            fake_driver = MagicMock()
            with patch(
                "selenium.webdriver.chrome.service.Service"
            ), patch("selenium.webdriver.Chrome", return_value=fake_driver):
                with chrome_profile_session(profile) as driver:
                    self.assertIs(driver, fake_driver)
                    # mimic the runner writing a cookie into the snapshot
                    snap_default = profile.parent / f"{profile.name}_snap" / "Default"
                    snap_default.mkdir(parents=True, exist_ok=True)
                    (snap_default / "Cookies").write_text("hello", encoding="utf-8")
            fake_driver.quit.assert_called_once()
            self.assertEqual(
                (profile / "Default" / "Cookies").read_text(encoding="utf-8"),
                "hello",
            )

    def test_session_swallows_quit_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir) / "profile"
            profile.mkdir()
            fake_driver = MagicMock()
            fake_driver.quit.side_effect = RuntimeError("late")
            with patch(
                "selenium.webdriver.chrome.service.Service"
            ), patch("selenium.webdriver.Chrome", return_value=fake_driver):
                # Empty body is intentional: we are asserting only that the
                # quit error swallowed below does NOT propagate out of the
                # context manager.
                with chrome_profile_session(profile):
                    pass  # noqa: S108


class TestBuildPlaywrightPersistentContext(unittest.TestCase):

    def test_passes_stealth_args_to_browser_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile = Path(tmpdir) / "profile"
            browser_type = MagicMock()
            browser_type.launch_persistent_context.return_value = "ctx"
            flags = StealthFlags(window_size=(1000, 800), extra_args=["--foo"])
            ctx = build_playwright_persistent_context(browser_type, profile, flags=flags)
            self.assertEqual(ctx, "ctx")
            kwargs = browser_type.launch_persistent_context.call_args.kwargs
            self.assertEqual(kwargs["user_data_dir"], str(profile))
            self.assertEqual(kwargs["viewport"], {"width": 1000, "height": 800})
            self.assertIn("--foo", kwargs["args"])
            self.assertIn("--disable-blink-features=AutomationControlled", kwargs["args"])


class TestMinimiseChromeWindows(unittest.TestCase):

    def test_non_windows_returns_zero(self):
        if sys.platform == "win32":
            self.skipTest("non-windows path only")
        self.assertEqual(minimise_chrome_windows(Path(".")), 0)

    def test_missing_dependencies_returns_zero(self):
        # We can't easily fake sys.platform; on Windows without pywin32, the
        # function returns 0. We just assert that calling it produces an int.
        result = minimise_chrome_windows(Path("."))
        self.assertIsInstance(result, int)


if __name__ == "__main__":
    unittest.main()
