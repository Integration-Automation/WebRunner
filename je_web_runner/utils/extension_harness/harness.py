"""
Browser 擴充測試輔助：解析 manifest.json，配置 Selenium / Playwright 載入路徑。
Light harness for testing browser extensions:

- :func:`parse_manifest` reads ``manifest.json`` (MV2 or MV3) and returns
  the salient metadata (id, version, popup path, background script).
- :func:`apply_to_chrome_options` adds ``--load-extension`` flags for a
  Selenium ``ChromeOptions`` instance.
- :func:`playwright_persistent_context_args` returns the kwargs needed
  for ``browser_type.launch_persistent_context(...)`` so a packed
  extension is loaded.

Firefox uses a different loading model (``WebDriver: install addon``);
that path is intentionally out of scope here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ExtensionHarnessError(WebRunnerException):
    """Raised when manifest is malformed or extension dir is invalid."""


@dataclass
class ExtensionInfo:
    name: str
    version: str
    manifest_version: int
    popup: Optional[str] = None
    background_script: Optional[str] = None
    permissions: Optional[List[str]] = None
    extension_dir: Optional[str] = None


def parse_manifest(manifest: Union[str, Path, Dict[str, Any]]) -> ExtensionInfo:
    """Parse a manifest dict / file path into :class:`ExtensionInfo`."""
    if isinstance(manifest, (str, Path)):
        path = Path(manifest)
        if path.is_dir():
            path = path / "manifest.json"
        if not path.is_file():
            raise ExtensionHarnessError(f"manifest not found: {manifest!r}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ExtensionHarnessError(f"manifest invalid JSON: {error}") from error
    elif isinstance(manifest, dict):
        data = manifest
    else:
        raise ExtensionHarnessError("manifest must be path or dict")
    name = data.get("name")
    version = data.get("version")
    manifest_version = data.get("manifest_version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ExtensionHarnessError("manifest missing 'name' / 'version'")
    if manifest_version not in (2, 3):
        raise ExtensionHarnessError(
            f"manifest_version must be 2 or 3, got {manifest_version!r}"
        )
    popup = _popup_path(data, manifest_version)
    background = _background_script(data, manifest_version)
    return ExtensionInfo(
        name=name,
        version=version,
        manifest_version=int(manifest_version),
        popup=popup,
        background_script=background,
        permissions=list(data.get("permissions") or []),
    )


def _popup_path(data: Dict[str, Any], manifest_version: int) -> Optional[str]:
    action_key = "action" if manifest_version == 3 else "browser_action"
    action = data.get(action_key) or {}
    popup = action.get("default_popup")
    return popup if isinstance(popup, str) else None


def _background_script(data: Dict[str, Any], manifest_version: int) -> Optional[str]:
    background = data.get("background") or {}
    if manifest_version == 3:
        worker = background.get("service_worker")
        return worker if isinstance(worker, str) else None
    scripts = background.get("scripts")
    if isinstance(scripts, list) and scripts:
        return str(scripts[0])
    page = background.get("page")
    return page if isinstance(page, str) else None


def extension_info(directory: Union[str, Path]) -> ExtensionInfo:
    """Convenience: parse manifest under ``directory`` and stamp ``extension_dir``."""
    info = parse_manifest(directory)
    info.extension_dir = str(Path(directory).resolve())
    return info


def apply_to_chrome_options(options: Any, extensions: Iterable[Union[str, Path]]) -> Any:
    """
    給 Selenium ``ChromeOptions`` 加上 ``--load-extension``。
    Add ``--load-extension`` flags for each unpacked extension directory.
    """
    if not hasattr(options, "add_argument"):
        raise ExtensionHarnessError("options object must expose add_argument()")
    paths = [str(Path(ext).resolve()) for ext in extensions]
    for path in paths:
        if not Path(path).is_dir():
            raise ExtensionHarnessError(f"extension directory missing: {path!r}")
    if paths:
        options.add_argument(f"--load-extension={','.join(paths)}")
        options.add_argument("--disable-extensions-except=" + ",".join(paths))
    return options


def playwright_persistent_context_args(
    extensions: Iterable[Union[str, Path]],
    user_data_dir: Union[str, Path],
    headless: bool = False,
) -> Dict[str, Any]:
    """
    Return kwargs for Playwright's ``launch_persistent_context``.

    Playwright requires a persistent context to load a packed extension;
    headless mode is unreliable for MV3 service workers so the default
    is ``headless=False``.
    """
    paths = [str(Path(ext).resolve()) for ext in extensions]
    for path in paths:
        if not Path(path).is_dir():
            raise ExtensionHarnessError(f"extension directory missing: {path!r}")
    args: List[str] = []
    if paths:
        args.extend([
            f"--disable-extensions-except={','.join(paths)}",
            f"--load-extension={','.join(paths)}",
        ])
    return {
        "user_data_dir": str(user_data_dir),
        "headless": headless,
        "args": args,
    }
