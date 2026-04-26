"""Device-emulation presets (viewport + UA + DPR + touch)."""
from je_web_runner.utils.device_emulation.presets import (
    DeviceEmulationError,
    DevicePreset,
    apply_to_chrome_options,
    available_presets,
    get_preset,
    playwright_kwargs,
)

__all__ = [
    "DeviceEmulationError",
    "DevicePreset",
    "apply_to_chrome_options",
    "available_presets",
    "get_preset",
    "playwright_kwargs",
]
