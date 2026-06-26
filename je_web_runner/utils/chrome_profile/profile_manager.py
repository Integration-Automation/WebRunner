"""
持久化 Chrome profile：snapshot → 跑 → sync-back 模式 + SingletonLock 清理 + stealth flag。
Persistent Chrome profile helpers: snapshot-launch-sync pattern, singleton-lock
cleanup, stealth flags, fake user-agent. Mirrors the pattern proven in
Jeffrey_RPA's NovelAI scraper where the actual `.chrome_profile/` directory is
often locked by Defender / OneDrive / Explorer; we copy session-critical files
into a disposable snapshot, run Chrome against that, and sync the login state
back on exit.

Supports Selenium (Options builder + driver factory) and Playwright (persistent
context launch).
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, List, Optional, Sequence, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ChromeProfileError(WebRunnerException):
    """Raised on snapshot / sync-back / spawn problems."""


# Files Chrome leaves in user-data-dir on unclean exit. A new Chrome that
# sees any of these will refuse to launch with the same profile
# (SessionNotCreatedException). Removing them is safe — they do NOT contain
# cookies or login data.
SINGLETON_LOCK_FILES: Tuple[str, ...] = (
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "lockfile",
    "RunningChromeVersion",
)

# Relative paths inside the profile that we treat as session-critical:
# everything we need to preserve a logged-in session. The journal sidecar
# files are SQLite WAL artefacts and must be copied alongside the main DB.
SESSION_CRITICAL_PATHS: Tuple[str, ...] = (
    "Default/Cookies",
    "Default/Cookies-journal",
    "Default/Login Data",
    "Default/Login Data-journal",
    "Default/Login Data For Account",
    "Default/Login Data For Account-journal",
    "Default/Web Data",
    "Default/Web Data-journal",
    "Default/Preferences",
    "Default/Secure Preferences",
    "Default/History",
    "Default/Bookmarks",
    "Local State",
    "First Run",
)

# Directories we strip from the snapshot — disposable caches that Chrome
# rebuilds on demand. Keeping them in sync bloats the snapshot tenfold and
# slows every launch.
SNAPSHOT_IGNORE_NAMES: frozenset = frozenset({
    "Cache", "Code Cache", "GPUCache", "ShaderCache",
    "GraphiteDawnCache", "DawnGraphiteCache", "GrShaderCache",
    "Service Worker", "blob_storage", "Crashpad", "CrashpadMetrics",
    "Subresource Filter", "optimization_guide_model_store",
    "Download Service", "VideoDecodeStats", "Trust Tokens",
    "Network", "Session Storage", "IndexedDB",
})

# Realistic desktop Chrome user-agent. Update periodically — Chrome bumps
# the major version every ~6 weeks and stale UA strings raise some
# anti-bot heuristics.
DEFAULT_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


@dataclass
class StealthFlags:
    """
    可序列化的 stealth 設定，方便由 action JSON 帶入。
    Serialisable stealth knobs so action JSON can configure them.
    """
    user_agent: str = DEFAULT_USER_AGENT
    language: str = "en-US"
    window_size: Optional[Tuple[int, int]] = None
    disable_blink_features: bool = True
    exclude_automation_switches: bool = True
    headless: bool = False
    extra_args: List[str] = field(default_factory=list)


def cleanup_chrome_locks(profile_dir: Path) -> List[str]:
    """
    清理 SingletonLock / lockfile 等殘留檔。Locked file 改用 rename 規避。
    Remove the singleton lock files Chrome leaves behind. Files held by the
    OS get renamed (which Windows usually allows) so a fresh Chrome can
    create its own lock. Returns a per-file status list for logging.
    """
    profile_dir = Path(profile_dir)
    if not profile_dir.exists():
        return []
    statuses: List[str] = []
    for fname in SINGLETON_LOCK_FILES:
        target = profile_dir / fname
        if not target.exists() and not target.is_symlink():
            continue
        try:
            target.unlink()
            statuses.append(f"removed {fname}")
        except OSError:
            try:
                renamed = profile_dir / f"{fname}.stale.{int(time.time())}"
                target.rename(renamed)
                statuses.append(f"renamed {fname} → {renamed.name}")
            except OSError as error:
                statuses.append(f"failed {fname}: {error!r}")
    if statuses:
        web_runner_logger.info(f"cleanup_chrome_locks: {statuses}")
    return statuses


def _is_session_critical(rel_path: str) -> bool:
    """Test whether ``rel_path`` (POSIX-style) is in the session-critical list."""
    normalised = rel_path.replace("\\", "/")
    return normalised in SESSION_CRITICAL_PATHS


def snapshot_chrome_profile(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    profile_dir: Path,
    snapshot_dir: Path,
    *,
    full_copy: bool = False,
) -> Path:
    """
    把 profile 複製到 snapshot_dir，跳過 cache / lock。
    Copy the profile into a disposable snapshot directory, skipping cache
    folders and singleton locks. ``full_copy=True`` copies everything except
    the lock files (useful for migrations where you want extensions too).

    Returns the snapshot path. Per-file copy errors are swallowed and
    logged — partial snapshots are still usable since session-critical
    files are independent of cache files.
    """
    profile_dir = Path(profile_dir)
    snapshot_dir = Path(snapshot_dir)
    if not profile_dir.exists():
        raise ChromeProfileError(f"profile dir does not exist: {profile_dir}")

    if snapshot_dir.exists():
        try:
            shutil.rmtree(snapshot_dir)
        except OSError as error:
            raise ChromeProfileError(
                f"cannot clear previous snapshot at {snapshot_dir}: {error!r}"
            ) from error
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    skipped: List[str] = []
    profile_root_str = str(profile_dir)
    for root, dirs, files in os.walk(profile_dir, topdown=True):
        if not full_copy:
            dirs[:] = [d for d in dirs if d not in SNAPSHOT_IGNORE_NAMES]
        rel_root = os.path.relpath(root, profile_root_str)
        target_root = snapshot_dir if rel_root == "." else snapshot_dir / rel_root
        target_root.mkdir(parents=True, exist_ok=True)
        for fname in files:
            if fname in SINGLETON_LOCK_FILES:
                continue
            src = Path(root) / fname
            dst = target_root / fname
            try:
                shutil.copy2(src, dst)
                copied += 1
            except OSError as error:  # shutil.Error is a subclass of OSError
                skipped.append(f"{rel_root}/{fname}: {error!r}")
    web_runner_logger.info(
        f"snapshot_chrome_profile: copied={copied} skipped={len(skipped)} → {snapshot_dir}"
    )
    if skipped and len(skipped) < 30:
        web_runner_logger.info(f"snapshot skipped detail: {skipped}")
    return snapshot_dir


def sync_chrome_profile_back(
    snapshot_dir: Path,
    profile_dir: Path,
    *,
    paths: Sequence[str] = SESSION_CRITICAL_PATHS,
) -> List[str]:
    """
    把 snapshot 內 session-critical 檔複製回原 profile。
    Copy session-critical files from the snapshot back into the persistent
    profile so a future run picks up the latest cookies / login data.
    Returns a list of "copied" / "skipped" status strings for logging.
    """
    snapshot_dir = Path(snapshot_dir)
    profile_dir = Path(profile_dir)
    if not snapshot_dir.exists():
        raise ChromeProfileError(f"snapshot dir does not exist: {snapshot_dir}")
    profile_dir.mkdir(parents=True, exist_ok=True)

    statuses: List[str] = []
    for rel in paths:
        src = snapshot_dir / rel
        if not src.exists():
            continue
        dst = profile_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dst)
            statuses.append(f"copied {rel}")
        except OSError as error:  # shutil.Error is a subclass of OSError
            statuses.append(f"skipped {rel}: {error!r}")
    web_runner_logger.info(f"sync_chrome_profile_back: {len(statuses)} entries")
    return statuses


def build_chrome_options(
    profile_dir: Path,
    flags: Optional[StealthFlags] = None,
):
    """
    產出帶 stealth 設定的 ChromeOptions。
    Build a Selenium ``ChromeOptions`` instance with stealth flags, the
    given user-data-dir and (optionally) a real desktop UA.
    """
    from selenium.webdriver.chrome.options import Options as ChromeOptions  # local import keeps the module import-light
    flags = flags or StealthFlags()
    profile_dir = Path(profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    opts = ChromeOptions()
    if flags.headless:
        opts.add_argument("--headless=new")
    if flags.disable_blink_features:
        opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(f"--lang={flags.language}")
    opts.add_argument(f"--user-agent={flags.user_agent}")
    opts.add_argument(f"--user-data-dir={profile_dir}")
    if flags.window_size:
        width, height = flags.window_size
        opts.add_argument(f"--window-size={int(width)},{int(height)}")
    for arg in flags.extra_args:
        opts.add_argument(arg)
    if flags.exclude_automation_switches:
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
    return opts


def build_stealth_chrome_driver(
    profile_dir: Path,
    *,
    snapshot_dir: Optional[Path] = None,
    flags: Optional[StealthFlags] = None,
    chromedriver_log: Optional[Path] = None,
    retry_once: bool = True,
):
    """
    Spawn Chrome 用 snapshot profile + stealth flags + 一次 retry。
    Spawn a Selenium Chrome driver against a *snapshot* of the persistent
    profile to side-step file locks held by AV / OneDrive / Explorer.
    Caller is responsible for calling ``sync_chrome_profile_back`` on quit
    if they want to preserve cookies — or use ``chrome_profile_session``.

    Returns ``(driver, snapshot_path)``. ``snapshot_path`` is ``None`` when
    ``snapshot_dir`` is falsy (driver runs directly against ``profile_dir``).
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService

    profile_dir = Path(profile_dir)
    flags = flags or StealthFlags()

    if snapshot_dir is not None:
        snapshot_path = snapshot_chrome_profile(profile_dir, Path(snapshot_dir))
        cleanup_chrome_locks(snapshot_path)
        run_dir = snapshot_path
    else:
        snapshot_path = None
        cleanup_chrome_locks(profile_dir)
        run_dir = profile_dir

    opts = build_chrome_options(run_dir, flags=flags)
    service_kwargs = {}
    if chromedriver_log is not None:
        service_kwargs["log_path"] = str(chromedriver_log)
    try:
        service = ChromeService(**service_kwargs)
        driver = webdriver.Chrome(service=service, options=opts)
    except Exception as first_err:
        if not retry_once:
            raise ChromeProfileError(
                f"chrome spawn failed: {first_err!r}"
            ) from first_err
        web_runner_logger.warning(
            f"first chrome spawn failed: {first_err!r}; rebuilding snapshot and retrying"
        )
        if snapshot_path is not None:
            snapshot_path = snapshot_chrome_profile(profile_dir, Path(snapshot_dir))
            cleanup_chrome_locks(snapshot_path)
            run_dir = snapshot_path
            opts = build_chrome_options(run_dir, flags=flags)
        time.sleep(1.5)
        try:
            service = ChromeService(**service_kwargs)
            driver = webdriver.Chrome(service=service, options=opts)
        except Exception as second_err:
            raise ChromeProfileError(
                f"chrome spawn failed twice: {second_err!r}"
            ) from second_err
    web_runner_logger.info(
        f"stealth chrome driver spawned: profile={profile_dir} snapshot={snapshot_path}"
    )
    return driver, snapshot_path


@contextmanager
def chrome_profile_session(
    profile_dir: Path,
    *,
    snapshot_dir: Optional[Path] = None,
    flags: Optional[StealthFlags] = None,
    chromedriver_log: Optional[Path] = None,
    sync_back: bool = True,
) -> Iterator[Any]:
    """
    Context manager：spawn driver → yield → quit → sync-back。
    Context-managed lifecycle. ``snapshot_dir`` defaults to
    ``profile_dir.parent / (profile_dir.name + "_snap")``. The yielded
    value is the Selenium driver; on exit we quit the driver and sync
    session-critical files back into the persistent profile.
    """
    profile_dir = Path(profile_dir)
    if snapshot_dir is None:
        snapshot_dir = profile_dir.parent / f"{profile_dir.name}_snap"
    driver, snapshot_path = build_stealth_chrome_driver(
        profile_dir,
        snapshot_dir=snapshot_dir,
        flags=flags,
        chromedriver_log=chromedriver_log,
    )
    try:
        yield driver
    finally:
        try:
            driver.quit()
        except Exception as error:
            web_runner_logger.warning(f"driver.quit failed: {error!r}")
        if sync_back and snapshot_path is not None:
            try:
                sync_chrome_profile_back(snapshot_path, profile_dir)
            except ChromeProfileError as error:
                web_runner_logger.warning(f"sync_back failed: {error!r}")


def build_playwright_persistent_context(
    playwright_browser_type: Any,
    profile_dir: Path,
    *,
    flags: Optional[StealthFlags] = None,
    extra_launch_kwargs: Optional[dict] = None,
) -> Any:
    """
    用 Playwright 的 persistent context 開瀏覽器並套 stealth flag。
    Launch Playwright with ``launch_persistent_context``, passing stealth
    flags and a stable user-agent. Caller passes the chromium browser type
    (e.g. ``playwright.chromium``); we do not import playwright at module
    load time because it is an optional dependency.

    Returns a ``BrowserContext`` ready to ``new_page()``.
    """
    flags = flags or StealthFlags()
    profile_dir = Path(profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    cleanup_chrome_locks(profile_dir)

    args: List[str] = [f"--lang={flags.language}"]
    if flags.disable_blink_features:
        args.append("--disable-blink-features=AutomationControlled")
    args.extend(flags.extra_args)

    launch_kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": flags.headless,
        "user_agent": flags.user_agent,
        "args": args,
    }
    if flags.window_size:
        launch_kwargs["viewport"] = {
            "width": int(flags.window_size[0]),
            "height": int(flags.window_size[1]),
        }
    if extra_launch_kwargs:
        launch_kwargs.update(extra_launch_kwargs)
    web_runner_logger.info(
        f"playwright persistent context launching: profile={profile_dir}"
    )
    return playwright_browser_type.launch_persistent_context(**launch_kwargs)


# ----- optional Windows-only window minimise hook --------------------------

def minimise_chrome_windows(profile_dir: Path) -> int:
    """
    Win32 路徑 minimise 所有跑這個 profile 的 chrome.exe 視窗。
    Best-effort: enumerate top-level windows whose owner chrome.exe has a
    cmdline arg referencing ``profile_dir``, and ``ShowWindow(SW_MINIMIZE)``
    each. Returns the count of windows hidden. No-op on non-Windows or when
    pywin32 / psutil is unavailable.
    """
    if sys.platform != "win32":
        return 0
    try:
        import psutil  # type: ignore
        import win32con  # type: ignore
        import win32gui  # type: ignore
        import win32process  # type: ignore
    except ImportError:
        web_runner_logger.info(
            "minimise_chrome_windows: pywin32/psutil not installed; skipping"
        )
        return 0

    profile_marker = str(Path(profile_dir)).replace("\\", "/").lower()
    target_pids = set()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name != "chrome.exe":
                continue
            cmdline = " ".join(proc.info.get("cmdline") or []).replace("\\", "/").lower()
            if profile_marker in cmdline:
                target_pids.add(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    hidden = 0

    def _maybe_minimise(hwnd, _arg):
        nonlocal hidden
        if not win32gui.IsWindowVisible(hwnd):
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid in target_pids:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            hidden += 1

    win32gui.EnumWindows(_maybe_minimise, None)
    web_runner_logger.info(f"minimise_chrome_windows: hidden={hidden}")
    return hidden
