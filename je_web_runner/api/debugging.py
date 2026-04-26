"""Façade: cross browser parity / pr comment / extension harness."""
from je_web_runner.utils.cross_browser.parity import (
    BrowserRunResult,
    CrossBrowserError,
    ParityFinding,
    ParityReport,
    assert_parity,
    diff_runs,
)
from je_web_runner.utils.extension_harness.harness import (
    ExtensionHarnessError,
    ExtensionInfo,
    apply_to_chrome_options as apply_extension_to_chrome_options,
    extension_info,
    parse_manifest,
    playwright_persistent_context_args,
)
from je_web_runner.utils.pr_comment.poster import (
    PrCommentError,
    PrSummary,
    build_summary_markdown,
    post_or_update_comment,
)

__all__ = [
    "BrowserRunResult", "CrossBrowserError", "ParityFinding", "ParityReport",
    "assert_parity", "diff_runs",
    "ExtensionHarnessError", "ExtensionInfo",
    "apply_extension_to_chrome_options", "extension_info",
    "parse_manifest", "playwright_persistent_context_args",
    "PrCommentError", "PrSummary",
    "build_summary_markdown", "post_or_update_comment",
]
