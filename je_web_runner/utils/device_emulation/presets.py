"""
裝置仿真設定包：viewport / device pixel ratio / user-agent / 是否 touch。
Device-emulation presets compatible with both Chrome DevTools Protocol
(via ``Emulation.setDeviceMetricsOverride``) and Playwright
(``browser.new_context(**playwright_kwargs)``).

Profiles intentionally limited to popular reference devices; users can
extend via :func:`register_preset`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from je_web_runner.utils.exception.exceptions import WebRunnerException


class DeviceEmulationError(WebRunnerException):
    """Raised when an unknown preset is requested or driver isn't supported."""


@dataclass(frozen=True)
class DevicePreset:
    name: str
    width: int
    height: int
    device_scale_factor: float
    is_mobile: bool
    has_touch: bool
    user_agent: str


_PRESETS: Dict[str, DevicePreset] = {
    "iPhone 15 Pro": DevicePreset(
        name="iPhone 15 Pro",
        width=393, height=852, device_scale_factor=3.0,
        is_mobile=True, has_touch=True,
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    ),
    "iPhone SE": DevicePreset(
        name="iPhone SE",
        width=375, height=667, device_scale_factor=2.0,
        is_mobile=True, has_touch=True,
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        ),
    ),
    "Pixel 8": DevicePreset(
        name="Pixel 8",
        width=412, height=915, device_scale_factor=2.625,
        is_mobile=True, has_touch=True,
        user_agent=(
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
    ),
    "Galaxy S23": DevicePreset(
        name="Galaxy S23",
        width=360, height=780, device_scale_factor=3.0,
        is_mobile=True, has_touch=True,
        user_agent=(
            "Mozilla/5.0 (Linux; Android 14; SM-S911U) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36"
        ),
    ),
    "iPad Pro 11": DevicePreset(
        name="iPad Pro 11",
        width=834, height=1194, device_scale_factor=2.0,
        is_mobile=True, has_touch=True,
        user_agent=(
            "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    ),
    "Desktop 1080p": DevicePreset(
        name="Desktop 1080p",
        width=1920, height=1080, device_scale_factor=1.0,
        is_mobile=False, has_touch=False,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
    ),
    "Desktop 4K": DevicePreset(
        name="Desktop 4K",
        width=3840, height=2160, device_scale_factor=2.0,
        is_mobile=False, has_touch=False,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ),
    ),
}


def available_presets() -> List[str]:
    return sorted(_PRESETS.keys())


def get_preset(name: str) -> DevicePreset:
    if name not in _PRESETS:
        raise DeviceEmulationError(
            f"unknown device preset {name!r}; available: {available_presets()}"
        )
    return _PRESETS[name]


def register_preset(preset: DevicePreset) -> None:
    """Replace or add a preset by name."""
    if not isinstance(preset, DevicePreset):
        raise DeviceEmulationError("preset must be a DevicePreset instance")
    _PRESETS[preset.name] = preset


def playwright_kwargs(preset_name: str) -> Dict[str, Any]:
    """Return ``new_context`` kwargs for Playwright."""
    preset = get_preset(preset_name)
    return {
        "viewport": {"width": preset.width, "height": preset.height},
        "device_scale_factor": preset.device_scale_factor,
        "is_mobile": preset.is_mobile,
        "has_touch": preset.has_touch,
        "user_agent": preset.user_agent,
    }


def apply_to_chrome_options(options: Any, preset_name: str) -> Any:
    """
    Add Chrome ``--window-size`` / ``--user-agent`` for a Selenium ``ChromeOptions``.
    """
    preset = get_preset(preset_name)
    if not hasattr(options, "add_argument"):
        raise DeviceEmulationError("options object must expose add_argument()")
    options.add_argument(f"--window-size={preset.width},{preset.height}")
    options.add_argument(f"--user-agent={preset.user_agent}")
    return options


def cdp_emulation_command(preset_name: str) -> Dict[str, Any]:
    """Return the CDP ``Emulation.setDeviceMetricsOverride`` payload."""
    preset = get_preset(preset_name)
    return {
        "width": preset.width,
        "height": preset.height,
        "deviceScaleFactor": preset.device_scale_factor,
        "mobile": preset.is_mobile,
        "screenWidth": preset.width,
        "screenHeight": preset.height,
    }
