"""Cross-browser parity testing: run identical actions and diff results."""
from je_web_runner.utils.cross_browser.parity import (
    CrossBrowserError,
    ParityFinding,
    ParityReport,
    diff_runs,
)

__all__ = [
    "CrossBrowserError",
    "ParityFinding",
    "ParityReport",
    "diff_runs",
]
