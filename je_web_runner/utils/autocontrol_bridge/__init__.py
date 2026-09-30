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

__all__ = [
    "DENIED_COMMANDS", "DENIED_PREFIXES", "AutoControlBridgeError",
    "ac_available", "ac_list_commands", "ac_run", "ac_run_actions",
]
