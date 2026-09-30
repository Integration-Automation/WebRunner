"""Facade: Browser and driver platform: CDP, BiDi, profiles, extensions, grids, desktop bridge, CLI."""
from je_web_runner.utils.autocontrol_bridge.bridge import (
    AutoControlBridgeError, ac_available, ac_executor, is_denied, ac_list_commands, ac_run_actions, ac_run,
)
from je_web_runner.utils.autocontrol_bridge.native import (
    invisible_reason, require_visible_browser, fill_native_file_dialog, assert_image_on_screen,
    click_element_native,
)
from je_web_runner.utils.autocontrol_bridge.screen_mapping import (
    ScreenMappingError, element_center_on_screen,
)
from je_web_runner.utils.bidi.network import (
    BidiNetworkError, add_request_handler, add_response_handler, add_auth_handler, clear_network_handlers,
)
from je_web_runner.utils.bidi.selenium_events import (
    BidiEventsError, SeleniumBidiEvents, to_bidi_url_pattern,
)
from je_web_runner.utils.cdp.cdp_commands import (
    CDPError, selenium_cdp, playwright_cdp, reset_playwright_cdp_sessions,
)
from je_web_runner.utils.cdp.event_loop import (
    CDPEventLoopError, resolve_cdp_ws_url, CDPEventListener,
)
from je_web_runner.utils.cdp.tracing import (
    TracingError, record_trace,
)
from je_web_runner.utils.chrome_profile.profile_manager import (
    ChromeProfileError, StealthFlags, cleanup_chrome_locks, snapshot_chrome_profile, sync_chrome_profile_back,
    build_chrome_options, build_stealth_chrome_driver, chrome_profile_session, build_playwright_persistent_context,
    minimise_chrome_windows,
)
from je_web_runner.utils.cli.cli_main import (
    main,
)
from je_web_runner.utils.cli.watch_mode import (
    watch_directory,
)
from je_web_runner.utils.cloud_grid.cloud_drivers import (
    CloudGridError, build_browserstack_capabilities, build_saucelabs_capabilities, build_lambdatest_capabilities,
    start_remote_driver, connect_browserstack, connect_saucelabs, connect_lambdatest,
)
from je_web_runner.utils.download_verify.verifier import (
    DownloadVerifyError, wait_for_download as download_verify_wait_for_download, sha256_of_file,
    assert_file_sha256, extract_pdf_text, assert_pdf_contains, assert_pdf_matches, read_csv_rows,
    assert_csv_columns, assert_csv_row_count, read_excel_rows, read_json_file, assert_json_matches_schema,
    DownloadAssertion, assert_download,
)
from je_web_runner.utils.driver_dispatch.js_eval import (
    DriverDispatchError, evaluate_expression, run_script,
)
from je_web_runner.utils.extensions.extension_loader import (
    ExtensionLoaderError, selenium_chrome_options_with_extension, playwright_extension_launch_args,
)
from je_web_runner.utils.file_transfer.file_helpers import (
    FileTransferError, selenium_upload_file, playwright_upload_file,
    wait_for_download as file_transfer_wait_for_download, list_new_downloads, snapshot_directory,
)
from je_web_runner.utils.locator_health.health_report import (
    LocatorHealthError, FallbackHitTracker, LocatorFinding, scan_action_file, scan_project, LocatorHealthReport,
    build_health_report, UpgradeSuggestion, suggest_upgrade, suggest_upgrades, apply_upgrades,
    render_health_markdown, save_health_report,
)
from je_web_runner.utils.scheduler.cron_runner import (
    SchedulerError, ScheduledRunner, schedule, run_scheduler_for, run_scheduler_forever, stop_scheduler,
    scheduler_counts, reset_scheduler,
)
from je_web_runner.utils.self_healing.healing_locator import (
    HealingError, HealingRegistry, find_with_healing_selenium, find_with_healing_playwright, register_fallback,
    register_fallbacks, clear_fallbacks,
)

__all__ = [
    "AutoControlBridgeError", "ac_available", "ac_executor", "is_denied", "ac_list_commands", "ac_run_actions",
    "ac_run", "invisible_reason", "require_visible_browser", "fill_native_file_dialog", "assert_image_on_screen",
    "click_element_native", "ScreenMappingError", "element_center_on_screen", "BidiNetworkError",
    "add_request_handler", "add_response_handler", "add_auth_handler", "clear_network_handlers", "BidiEventsError",
    "SeleniumBidiEvents", "to_bidi_url_pattern", "CDPError", "selenium_cdp", "playwright_cdp",
    "reset_playwright_cdp_sessions", "CDPEventLoopError", "resolve_cdp_ws_url", "CDPEventListener", "TracingError",
    "record_trace", "ChromeProfileError", "StealthFlags", "cleanup_chrome_locks", "snapshot_chrome_profile",
    "sync_chrome_profile_back", "build_chrome_options", "build_stealth_chrome_driver", "chrome_profile_session",
    "build_playwright_persistent_context", "minimise_chrome_windows", "main", "watch_directory", "CloudGridError",
    "build_browserstack_capabilities", "build_saucelabs_capabilities", "build_lambdatest_capabilities",
    "start_remote_driver", "connect_browserstack", "connect_saucelabs", "connect_lambdatest",
    "DownloadVerifyError", "download_verify_wait_for_download", "sha256_of_file", "assert_file_sha256",
    "extract_pdf_text", "assert_pdf_contains", "assert_pdf_matches", "read_csv_rows", "assert_csv_columns",
    "assert_csv_row_count", "read_excel_rows", "read_json_file", "assert_json_matches_schema", "DownloadAssertion",
    "assert_download", "DriverDispatchError", "evaluate_expression", "run_script", "ExtensionLoaderError",
    "selenium_chrome_options_with_extension", "playwright_extension_launch_args", "FileTransferError",
    "selenium_upload_file", "playwright_upload_file", "file_transfer_wait_for_download", "list_new_downloads",
    "snapshot_directory", "LocatorHealthError", "FallbackHitTracker", "LocatorFinding", "scan_action_file",
    "scan_project", "LocatorHealthReport", "build_health_report", "UpgradeSuggestion", "suggest_upgrade",
    "suggest_upgrades", "apply_upgrades", "render_health_markdown", "save_health_report", "SchedulerError",
    "ScheduledRunner", "schedule", "run_scheduler_for", "run_scheduler_forever", "stop_scheduler",
    "scheduler_counts", "reset_scheduler", "HealingError", "HealingRegistry", "find_with_healing_selenium",
    "find_with_healing_playwright", "register_fallback", "register_fallbacks", "clear_fallbacks",
]
