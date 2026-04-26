"""Browser extension test harness: load extensions, parse manifests, drive popups."""
from je_web_runner.utils.extension_harness.harness import (
    ExtensionHarnessError,
    ExtensionInfo,
    apply_to_chrome_options,
    extension_info,
    parse_manifest,
    playwright_persistent_context_args,
)

__all__ = [
    "ExtensionHarnessError",
    "ExtensionInfo",
    "apply_to_chrome_options",
    "extension_info",
    "parse_manifest",
    "playwright_persistent_context_args",
]
