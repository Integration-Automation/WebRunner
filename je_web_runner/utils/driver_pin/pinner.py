"""
Driver 版本固定：避免 webdriver_manager 每次跑都打 api.github.com。
Reads / writes ``.webrunner/drivers.json`` describing which geckodriver
or chromedriver version + URL to use, downloads the archive once into a
local cache, and returns the on-disk path so callers can pass it to
``Service(executable_path=...)``.
"""
from __future__ import annotations

import io
import json
import platform
import ssl
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class DriverPinError(WebRunnerException):
    """Raised when a pin file is invalid or download verification fails."""


@dataclass
class PinnedDriver:
    name: str            # "geckodriver" / "chromedriver" / "msedgedriver"
    version: str
    url: str             # direct download URL (CDN, GitHub release asset, etc.)
    archive_format: str  # "zip" | "tar.gz"
    binary_inside: str   # filename inside the archive
    platforms: List[str] = field(default_factory=list)
    cache_subdir: Optional[str] = None  # default: f"{name}/{version}"

    def matches_current_platform(self) -> bool:
        if not self.platforms:
            return True
        marker = current_platform_marker()
        return marker in self.platforms


def current_platform_marker() -> str:
    """Return ``win`` / ``mac-arm64`` / ``mac-x64`` / ``linux`` / ``linux-arm64``."""
    system = platform.system().lower()
    arch = platform.machine().lower()
    if system == "windows":
        return "win"
    if system == "darwin":
        return "mac-arm64" if arch in {"arm64", "aarch64"} else "mac-x64"
    if "arm" in arch or "aarch64" in arch:
        return "linux-arm64"
    return "linux"


def load_pinfile(path: Union[str, Path]) -> List[PinnedDriver]:
    fp = Path(path)
    if not fp.is_file():
        raise DriverPinError(f"pin file not found: {path!r}")
    try:
        document = json.loads(fp.read_text(encoding="utf-8"))
    except ValueError as error:
        raise DriverPinError(f"pin file is not JSON: {error}") from error
    drivers = document.get("drivers")
    if not isinstance(drivers, list):
        raise DriverPinError("pin file missing 'drivers' list")
    return [_pin_from_dict(index, entry) for index, entry in enumerate(drivers)]


def save_pinfile(path: Union[str, Path], drivers: List[PinnedDriver]) -> Path:
    fp = Path(path)
    fp.parent.mkdir(parents=True, exist_ok=True)
    document = {"drivers": [
        {
            "name": d.name,
            "version": d.version,
            "url": d.url,
            "archive_format": d.archive_format,
            "binary_inside": d.binary_inside,
            "platforms": list(d.platforms),
            "cache_subdir": d.cache_subdir,
        }
        for d in drivers
    ]}
    fp.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return fp


def _pin_from_dict(index: int, entry: Any) -> PinnedDriver:
    if not isinstance(entry, dict):
        raise DriverPinError(f"drivers[{index}] must be an object")
    for required in ("name", "version", "url", "archive_format", "binary_inside"):
        if required not in entry:
            raise DriverPinError(f"drivers[{index}] missing {required!r}")
    if entry["archive_format"] not in {"zip", "tar.gz"}:
        raise DriverPinError(
            f"drivers[{index}].archive_format must be zip / tar.gz, got "
            f"{entry['archive_format']!r}"
        )
    if not (entry["url"].startswith("https://") or entry["url"].startswith("http://")):  # NOSONAR — scheme allow-list
        raise DriverPinError(f"drivers[{index}].url must be http(s)")
    return PinnedDriver(
        name=str(entry["name"]),
        version=str(entry["version"]),
        url=str(entry["url"]),
        archive_format=str(entry["archive_format"]),
        binary_inside=str(entry["binary_inside"]),
        platforms=list(entry.get("platforms") or []),
        cache_subdir=entry.get("cache_subdir"),
    )


def download_pinned(
    pinned: PinnedDriver,
    cache_dir: Union[str, Path] = ".webrunner/drivers",
    fetch: Optional[Any] = None,
) -> Path:
    """
    確認對應的 driver 已下載並解壓；回傳可執行檔路徑
    Make sure the pinned driver archive has been fetched and extracted into
    ``cache_dir`` and return the on-disk path of the binary inside.

    ``fetch`` lets tests inject a synthetic byte loader; when ``None`` the
    archive is fetched via :func:`urllib.request.urlopen` over a default
    SSL context.
    """
    target_dir = Path(cache_dir) / (pinned.cache_subdir or f"{pinned.name}/{pinned.version}")
    target_binary = target_dir / pinned.binary_inside
    if target_binary.is_file():
        return target_binary
    target_dir.mkdir(parents=True, exist_ok=True)
    web_runner_logger.info(
        f"driver_pin downloading {pinned.name} {pinned.version} from {pinned.url}"
    )
    payload = (fetch or _default_fetch)(pinned.url)
    if not isinstance(payload, (bytes, bytearray)) or not payload:
        raise DriverPinError(f"empty payload for {pinned.url!r}")
    _extract_archive(pinned.archive_format, payload, target_dir)
    if not target_binary.is_file():
        raise DriverPinError(
            f"binary {pinned.binary_inside!r} not found inside archive"
        )
    try:
        target_binary.chmod(0o755)
    except OSError:
        pass  # Windows raises EBADF on chmod for some FS; binary is still usable
    return target_binary


def _default_fetch(url: str) -> bytes:
    if not (url.startswith("https://") or url.startswith("http://")):  # NOSONAR — guarded above
        raise DriverPinError(f"refusing non-http(s) url: {url!r}")
    ssl_context = ssl.create_default_context()  # NOSONAR — Py3.10+ default enforces TLS 1.2+
    with urllib.request.urlopen(url, context=ssl_context, timeout=120) as response:  # nosec B310 — scheme validated
        return response.read()


def _extract_archive(archive_format: str, payload: bytes, target_dir: Path) -> None:
    if archive_format == "zip":
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            _safe_extract_zip(zf, target_dir)
        return
    if archive_format == "tar.gz":
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tf:
            _safe_extract_tar(tf, target_dir)
        return
    raise DriverPinError(f"unsupported archive format {archive_format!r}")


def _safe_extract_zip(archive: zipfile.ZipFile, target_dir: Path) -> None:
    base = target_dir.resolve()
    for member in archive.namelist():
        candidate = (target_dir / member).resolve()
        try:
            candidate.relative_to(base)
        except ValueError as error:
            raise DriverPinError(f"unsafe zip member {member!r}") from error
    archive.extractall(target_dir)  # nosec B202 — members validated above


def _safe_extract_tar(archive: tarfile.TarFile, target_dir: Path) -> None:
    base = target_dir.resolve()
    for member in archive.getmembers():
        candidate = (target_dir / member.name).resolve()
        try:
            candidate.relative_to(base)
        except ValueError as error:
            raise DriverPinError(f"unsafe tar member {member.name!r}") from error
    archive.extractall(target_dir)  # nosec B202 — members validated above


def install_for_browser(
    pin_file: Union[str, Path],
    browser: str,
    cache_dir: Union[str, Path] = ".webrunner/drivers",
    fetch: Optional[Any] = None,
) -> Optional[Path]:
    """High-level helper: load the pin file, find the entry for ``browser``,
    download if needed, and return the on-disk binary path."""
    drivers = load_pinfile(pin_file)
    candidates = [
        d for d in drivers
        if d.name == _driver_name_for(browser) and d.matches_current_platform()
    ]
    if not candidates:
        return None
    return download_pinned(candidates[0], cache_dir=cache_dir, fetch=fetch)


def _driver_name_for(browser: str) -> str:
    return {
        "firefox": "geckodriver",
        "chrome": "chromedriver",
        "chromium": "chromedriver",
        "edge": "msedgedriver",
    }.get(browser.lower(), browser.lower())
