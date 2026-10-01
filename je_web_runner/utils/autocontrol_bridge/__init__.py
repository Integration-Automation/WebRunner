"""
AutoControl 橋接 / Drive the desktop through AutoControl (``je_auto_control``) from WebRunner.

Optional: install ``je_web_runner[autocontrol]``. Nothing here imports ``je_auto_control``
until a command runs.
"""
from je_web_runner.utils.autocontrol_bridge.bridge import (
    DENIED_COMMANDS,
    DENIED_PREFIXES,
    AutoControlBridgeError,
    ac_available,
    ac_list_commands,
    ac_run,
    ac_run_actions,
)
from je_web_runner.utils.autocontrol_bridge.native import (
    assert_image_on_screen,
    basic_auth_native,
    click_element_native,
    fill_native_file_dialog,
    invisible_reason,
    require_visible_browser,
)
from je_web_runner.utils.autocontrol_bridge.screen_mapping import ScreenMappingError, element_center_on_screen

__all__ = [
    "DENIED_COMMANDS", "DENIED_PREFIXES", "AutoControlBridgeError",
    "ac_available", "ac_list_commands", "ac_run", "ac_run_actions",
    "assert_image_on_screen", "basic_auth_native", "click_element_native", "fill_native_file_dialog",
    "invisible_reason", "require_visible_browser", "ScreenMappingError", "element_center_on_screen",
]
