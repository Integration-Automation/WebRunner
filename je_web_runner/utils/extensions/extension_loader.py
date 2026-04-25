"""
瀏覽器擴充功能載入：Chrome / Edge 系列接受 ``.crx`` 檔或解壓的目錄。
Browser-extension loaders for Chromium-family browsers. Selenium can take
either a packed ``.crx`` file or a flag to load an unpacked directory;
Playwright only supports the unpacked-directory flag (Chromium only).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from selenium.webdriver.chrome.options import Options as ChromeOptions

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ExtensionLoaderError(WebRunnerException):
    """Raised when an extension path is invalid for the chosen backend."""


def _check_path(path: str, expect_dir: bool = False) -> Path:
    target = Path(path)
    if not target.exists():
        raise ExtensionLoaderError(f"extension path not found: {path}")
    if expect_dir and not target.is_dir():
        raise ExtensionLoaderError(f"expected directory, got file: {path}")
    return target


def selenium_chrome_options_with_extension(
    crx_or_dir: str,
    options: Optional[ChromeOptions] = None,
) -> ChromeOptions:
    """
    回傳已掛上擴充功能的 ChromeOptions
    Build ChromeOptions configured to load a packed ``.crx`` file or an
    unpacked extension directory. Pass the result to ``WR_set_driver``.
    """
    web_runner_logger.info(f"selenium_chrome_options_with_extension: {crx_or_dir}")
    target = _check_path(crx_or_dir)
    opts = options or ChromeOptions()
    if target.is_file() and target.suffix.lower() == ".crx":
        opts.add_extension(str(target))
    else:
        opts.add_argument(f"--load-extension={target.resolve()}")
    return opts


def playwright_extension_launch_args(extension_dir: str) -> List[str]:
    """
    回傳給 ``pw_launch(args=...)`` 用的旗標清單（Chromium only）
    Build the ``args=[...]`` list to pass to ``pw_launch`` so the persistent
    context loads the unpacked extension at ``extension_dir``.

    Note: Playwright requires the headless mode to be off (``headless=False``)
    for most extensions to actually run.
    """
    web_runner_logger.info(f"playwright_extension_launch_args: {extension_dir}")
    target = _check_path(extension_dir, expect_dir=True)
    return [
        f"--disable-extensions-except={target.resolve()}",
        f"--load-extension={target.resolve()}",
    ]
