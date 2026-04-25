"""
檔案上傳 / 下載輔助工具。
File upload and download helpers for both backends, plus a directory poller
that waits for a new download to land.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

from selenium.webdriver.common.by import By

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


class FileTransferError(WebRunnerException):
    """Raised when an upload / download operation cannot proceed."""


def _check_file(path: str) -> Path:
    target = Path(path)
    if not target.exists() or not target.is_file():
        raise FileTransferError(f"upload file not found: {path}")
    return target.resolve()


def selenium_upload_file(input_selector: str, file_path: str) -> None:
    """
    對 ``<input type="file">`` 送入檔案路徑（Selenium）
    Send a file path to the targeted ``<input type="file">``.
    """
    web_runner_logger.info(f"selenium_upload_file: {input_selector} <- {file_path}")
    target = _check_file(file_path)
    driver = webdriver_wrapper_instance.current_webdriver
    if driver is None:
        raise FileTransferError("no Selenium driver active")
    element = driver.find_element(By.CSS_SELECTOR, input_selector)
    element.send_keys(str(target))


def playwright_upload_file(input_selector: str, file_path: str) -> None:
    """
    對指定的 file input 送入檔案（Playwright）
    Set a file path on the targeted input element via ``set_input_files``.
    """
    web_runner_logger.info(f"playwright_upload_file: {input_selector} <- {file_path}")
    target = _check_file(file_path)
    playwright_wrapper_instance.page.set_input_files(input_selector, str(target))


def wait_for_download(
    directory: str,
    timeout: float = 60.0,
    suffix: Optional[str] = None,
    poll_seconds: float = 0.5,
) -> str:
    """
    等待 ``directory`` 內出現新檔案（會跳過 ``.crdownload`` / ``.part``）
    Watch ``directory`` and return the path to the first newly-completed file.

    Skips Chrome's ``.crdownload`` and Firefox's ``.part`` markers; if
    ``suffix`` is given, the returned file's name must end with it (case
    insensitive).
    """
    base = Path(directory)
    if not base.is_dir():
        raise FileTransferError(f"download directory not found: {directory}")
    web_runner_logger.info(f"wait_for_download: {directory} timeout={timeout}")
    seen: set = {item.name for item in base.iterdir()}
    deadline = time.monotonic() + max(float(timeout), 0.0)
    suffix_lower = suffix.lower() if suffix else None
    while time.monotonic() < deadline:
        for item in base.iterdir():
            name = item.name
            if name in seen:
                continue
            if name.endswith(".crdownload") or name.endswith(".part"):
                continue
            if suffix_lower and not name.lower().endswith(suffix_lower):
                continue
            return str(item.resolve())
        time.sleep(poll_seconds)
    raise FileTransferError(
        f"no new download in {directory!r} within {timeout}s "
        f"(suffix filter: {suffix!r})"
    )


def list_new_downloads(directory: str, before: List[str]) -> List[str]:
    """
    回傳 ``directory`` 內目前存在但不在 ``before`` 清單中的檔案
    Diff helper: list paths currently in ``directory`` that were not in the
    pre-action snapshot ``before``.
    """
    base = Path(directory)
    if not base.is_dir():
        raise FileTransferError(f"download directory not found: {directory}")
    before_set = set(before or [])
    return [
        str(item.resolve())
        for item in base.iterdir()
        if str(item.resolve()) not in before_set
        and not item.name.endswith((".crdownload", ".part"))
    ]


def snapshot_directory(directory: str) -> List[str]:
    """Take a snapshot of resolved file paths under ``directory``."""
    base = Path(directory)
    if not base.is_dir():
        raise FileTransferError(f"directory not found: {directory}")
    return [str(item.resolve()) for item in base.iterdir() if item.is_file()]
