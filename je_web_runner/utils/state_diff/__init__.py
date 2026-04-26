"""Browser state diff: compare cookies + localStorage + sessionStorage snapshots."""
from je_web_runner.utils.state_diff.diff import (
    BrowserStateSnapshot,
    StateChanges,
    StateDiffError,
    capture_state,
    diff_states,
)

__all__ = [
    "BrowserStateSnapshot",
    "StateChanges",
    "StateDiffError",
    "capture_state",
    "diff_states",
]
