from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance
from je_web_runner.manager.webrunner_manager import get_webdriver_manager
from je_web_runner.webdriver.webdriver_with_options import set_webdriver_options_argument
from je_web_runner.utils.selenium_utils_wrapper.desired_capabilities.desired_capabilities import \
    get_desired_capabilities_keys, get_desired_capabilities
from je_web_runner.utils.selenium_utils_wrapper.keys.selenium_keys import Keys
from je_web_runner.utils.executor.action_executor import add_command_to_executor
from je_web_runner.utils.executor.action_executor import execute_action
from je_web_runner.utils.executor.action_executor import execute_files
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.file_process.get_dir_file_list import get_dir_files_as_list
from je_web_runner.utils.generate_report.generate_html_report import generate_html
from je_web_runner.utils.generate_report.generate_html_report import generate_html_report
from je_web_runner.utils.generate_report.generate_json_report import generate_json
from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.json.json_validator import validate_action_file
from je_web_runner.utils.json.json_validator import validate_action_files
from je_web_runner.utils.json.json_validator import validate_action_json
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml_report
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
from je_web_runner.utils.generate_report.generate_allure_report import generate_allure
from je_web_runner.utils.generate_report.generate_allure_report import generate_allure_report
from je_web_runner.utils.socket_server.web_runner_socket_server import encode_frame
from je_web_runner.utils.socket_server.web_runner_socket_server import read_frame
from je_web_runner.utils.socket_server.web_runner_socket_server import send_command
from je_web_runner.utils.socket_server.web_runner_socket_server import start_web_runner_socket_server
from je_web_runner.utils.test_object.test_object_class import TestObject
from je_web_runner.utils.test_object.test_object_class import create_test_object
from je_web_runner.utils.test_object.test_object_class import get_test_object_type_list
from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.utils.callback.callback_function_executor import callback_executor
from je_web_runner.utils.accessibility.axe_audit import (
    AccessibilityError,
    load_axe_source,
    playwright_run_audit,
    selenium_run_audit,
    summarise_violations,
)
from je_web_runner.utils.cdp.cdp_commands import (
    CDPError,
    playwright_cdp,
    reset_playwright_cdp_sessions,
    selenium_cdp,
)
from je_web_runner.utils.cdp.event_loop import (
    CDPEventListener,
    CDPEventLoopError,
    resolve_cdp_ws_url,
)
from je_web_runner.utils.cdp.tracing import (
    TracingError,
    record_trace,
)
from je_web_runner.utils.bidi.network import (
    BidiNetworkError,
    add_auth_handler as bidi_add_auth_handler,
    add_request_handler as bidi_add_request_handler,
    add_response_handler as bidi_add_response_handler,
    clear_network_handlers as bidi_clear_network_handlers,
)
from je_web_runner.utils.api.http_client import (
    HttpAssertionError,
    get_last_response,
    http_assert_json_contains,
    http_assert_status,
    http_delete,
    http_get,
    http_patch,
    http_post,
    http_put,
    http_request,
)
from je_web_runner.utils.data_driven.data_runner import (
    DataDrivenError,
    expand_with_row,
    load_dataset_csv,
    load_dataset_json,
    run_with_dataset,
)
from je_web_runner.utils.env_config.env_loader import EnvConfigError, expand_in_action, get_env, load_env
from je_web_runner.utils.pom_generator.pom_generator import (
    POMGeneratorError,
    extract_elements_from_html,
    generate_pom_class,
    generate_pom_from_html,
    generate_pom_from_url,
    write_pom_to_file,
)
from je_web_runner.utils.notifier.webhook_notifier import (
    NotifierError,
    notify_run_summary,
    notify_slack,
    notify_webhook,
    summarise_run,
)
from je_web_runner.utils.self_healing.healing_locator import (
    HealingError,
    HealingRegistry,
    clear_fallbacks,
    find_with_healing_playwright,
    find_with_healing_selenium,
    healing_registry,
    register_fallback,
    register_fallbacks,
)
from je_web_runner.utils.project.create_project_structure import create_project_dir
from je_web_runner.utils.visual_regression.visual_diff import capture_baseline as visual_capture_baseline
from je_web_runner.utils.visual_regression.visual_diff import compare_with_baseline as visual_compare_with_baseline
from je_web_runner.webdriver.playwright_wrapper import (
    PlaywrightBackendError,
    PlaywrightWrapper,
    playwright_wrapper_instance,
    pw_add_cookies,
    pw_back,
    pw_check,
    pw_clear_cookies,
    pw_click,
    pw_close_page,
    pw_content,
    pw_dblclick,
    pw_drag_and_drop,
    pw_evaluate,
    pw_fill,
    pw_find_element,
    pw_find_element_with_test_object_record,
    pw_find_elements,
    pw_find_elements_with_test_object_record,
    pw_forward,
    pw_get_cookies,
    pw_hover,
    pw_keyboard_down,
    pw_keyboard_press,
    pw_keyboard_type,
    pw_keyboard_up,
    pw_launch,
    pw_start_har_recording,
    pw_stop_har_recording,
    pw_route_mock,
    pw_route_mock_json,
    pw_route_unmock,
    pw_route_clear,
    pw_mouse_click,
    pw_mouse_down,
    pw_mouse_move,
    pw_mouse_up,
    pw_new_page,
    pw_page_count,
    pw_press,
    pw_quit,
    pw_refresh,
    pw_save_test_object_to_selector,
    pw_screenshot,
    pw_screenshot_bytes,
    pw_select_option,
    pw_set_default_navigation_timeout,
    pw_set_default_timeout,
    pw_set_viewport_size,
    pw_switch_to_page,
    pw_title,
    pw_to_url,
    pw_type_text,
    pw_uncheck,
    pw_url,
    pw_viewport_size,
    pw_wait_for_load_state,
    pw_wait_for_selector,
    pw_wait_for_timeout,
    pw_wait_for_url,
)
from je_web_runner.webdriver.playwright_element_wrapper import (
    PlaywrightElementWrapper,
    playwright_element_wrapper,
)
from je_web_runner.utils.recorder.browser_recorder import events_to_actions as recorder_events_to_actions
from je_web_runner.utils.recorder.browser_recorder import pull_events as recorder_pull_events
from je_web_runner.utils.recorder.browser_recorder import save_recording as recorder_save_recording
from je_web_runner.utils.recorder.browser_recorder import start_recording as recorder_start
from je_web_runner.utils.recorder.browser_recorder import stop_recording as recorder_stop
from je_web_runner.utils.chrome_profile.profile_manager import (
    ChromeProfileError,
    StealthFlags,
    build_chrome_options as chrome_profile_build_options,
    build_playwright_persistent_context,
    build_stealth_chrome_driver,
    chrome_profile_session,
    cleanup_chrome_locks,
    minimise_chrome_windows,
    snapshot_chrome_profile,
    sync_chrome_profile_back,
)
from je_web_runner.utils.failure_triage.triage import (
    FailureTriageError,
    TriageReport,
    TriageSignals,
    extract_signals_from_bundle,
    render_markdown as triage_render_markdown,
    save_report as triage_save_report,
    triage_bundle,
    triage_failure,
)
from je_web_runner.utils.flake_detector.detector import (
    FlakeDetectorError,
    FlakeScore,
    QuarantineEntry,
    QuarantineRegistry,
    compute_flake_scores,
    flaky_paths as flake_detector_flaky_paths,
    flaky_quarantine,
    quarantine_flaky,
    quarantine_report_markdown,
    release_if_stable,
)
from je_web_runner.utils.locator_health.health_report import (
    FallbackHitTracker,
    LocatorFinding,
    LocatorHealthError,
    LocatorHealthReport,
    UpgradeSuggestion as LocatorUpgradeSuggestion,
    apply_upgrades as locator_apply_upgrades,
    build_health_report as locator_build_health_report,
    fallback_hit_tracker,
    render_health_markdown as locator_render_health_markdown,
    save_health_report,
    scan_action_file as locator_scan_action_file,
    scan_project as locator_scan_project,
    suggest_upgrade as locator_suggest_upgrade,
    suggest_upgrades as locator_suggest_upgrades,
)
from je_web_runner.utils.device_cloud.real_device import (
    CloudCredentials,
    CloudSession,
    DeviceCloudError,
    RealDeviceCaps,
    build_capabilities as device_cloud_build_capabilities,
    connect_real_device,
    fetch_session_info,
    load_credentials as device_cloud_load_credentials,
    session_summary_markdown,
    update_session_status,
)
from je_web_runner.utils.otel_bridge.trace_bridge import (
    TraceBridgeError,
    TraceContext,
    bridged_span_playwright,
    bridged_span_selenium,
    clear_headers_playwright,
    clear_headers_selenium,
    current_otel_context,
    inject_headers_playwright,
    inject_headers_selenium,
    parse_traceparent,
    random_trace_context,
    trace_link,
)
from je_web_runner.utils.mutation_testing.mutator import (
    Mutation,
    MutationResult,
    MutationScore,
    MutationTestingError,
    MutationType,
    apply_mutation,
    assert_min_score as mutation_assert_min_score,
    generate_mutations,
    render_mutation_markdown,
    run_mutation_testing,
    run_mutation_testing_on_file,
)
from je_web_runner.utils.otp_interceptor.interceptor import (
    ImapProvider,
    InMemoryProvider as OtpInMemoryProvider,
    InterceptedMessage,
    MailHogProvider,
    MailpitProvider,
    OtpInterceptError,
    OtpProvider,
    WebhookSmsProvider,
    extract_otp_from_text,
    wait_for_otp,
)
from je_web_runner.utils.download_verify.verifier import (
    DownloadAssertion,
    DownloadVerifyError,
    assert_csv_columns,
    assert_csv_row_count,
    assert_download,
    assert_file_sha256,
    assert_json_matches_schema,
    assert_pdf_contains,
    assert_pdf_matches,
    extract_pdf_text,
    read_csv_rows,
    read_excel_rows,
    read_json_file,
    sha256_of_file,
    wait_for_download,
)
from je_web_runner.utils.test_auto_repair.repair import (
    RepairPlan,
    TestAutoRepairError,
    apply_repair,
    collect_git_diff,
    propose_repair,
    render_repair_markdown,
    repair_from_bundle,
)
from je_web_runner.utils.edge_case_generator.generator import (
    EdgeCase,
    EdgeCaseCategory,
    EdgeCaseGeneratorError,
    EdgeCaseSuite,
    generate_edge_cases,
    generate_edge_cases_from_file,
    render_suite_markdown as edge_case_render_markdown,
    write_suite_to_dir as edge_case_write_suite,
)
from je_web_runner.utils.openapi_to_e2e.generator import (
    GeneratedTest as OpenAPIGeneratedTest,
    GenerationResult as OpenAPIGenerationResult,
    OpenAPIGeneratorError,
    generate_tests_from_file as openapi_generate_from_file,
    generate_tests_from_spec as openapi_generate_from_spec,
    load_spec as openapi_load_spec,
    synthesize_example as openapi_synthesize_example,
    write_tests_to_dir as openapi_write_tests,
)
from je_web_runner.utils.cross_tab_sync.sync_assertions import (
    CrossTabSyncError,
    PropagationResult,
    assert_state_propagates,
    broadcast_message,
    collect_broadcast_messages,
    get_storage_value,
    install_broadcast_recorder,
    post_message_to_page,
    set_storage_value,
    wait_for_broadcast,
    wait_for_storage,
)
from je_web_runner.utils.visual_ai.perceptual import (
    HashResult as VisualHashResult,
    SimilarityResult as VisualSimilarityResult,
    VisualAIError,
    assert_visual_similar,
    average_hash as visual_average_hash,
    compare_images as visual_compare_images,
    difference_hash as visual_difference_hash,
    hamming_distance as visual_hamming_distance,
    hash_similarity as visual_hash_similarity,
    perceptual_hash as visual_perceptual_hash,
)
from je_web_runner.utils.test_scheduler.scheduler import (
    Schedule,
    TestCandidate,
    TestSchedulerError,
    build_candidates_from_ledger,
    render_schedule_markdown,
    schedule_tests,
    value_density as scheduler_value_density,
    value_of as scheduler_value_of,
)
from je_web_runner.utils.walkthrough_docs.generator import (
    Walkthrough,
    WalkthroughError,
    WalkthroughStep,
    build_walkthrough,
    collect_steps as walkthrough_collect_steps,
    narrate_steps as walkthrough_narrate_steps,
    render_confluence as walkthrough_render_confluence,
    render_markdown as walkthrough_render_markdown,
    save_walkthrough,
)
from je_web_runner.utils.live_dashboard.server import (
    DashboardConfig,
    DashboardServer,
    LiveDashboardError,
    build_summary as dashboard_build_summary,
)
__all__ = [
    "web_element_wrapper", "set_webdriver_options_argument",
    "webdriver_wrapper_instance", "get_webdriver_manager",
    "get_desired_capabilities", "get_desired_capabilities_keys", "add_command_to_executor",
    "execute_action", "execute_files", "executor",
    "generate_html", "generate_html_report",
    "generate_json", "generate_json_report", "read_action_json",
    "generate_xml", "generate_xml_report",
    "generate_junit_xml", "generate_junit_xml_report",
    "generate_allure", "generate_allure_report",
    "start_web_runner_socket_server", "get_dir_files_as_list",
    "send_command", "read_frame", "encode_frame",
    "TestObject", "create_test_object", "get_test_object_type_list",
    "test_record_instance", "Keys", "callback_executor", "create_project_dir",
    "load_env", "get_env", "expand_in_action", "EnvConfigError",
    "load_dataset_csv", "load_dataset_json", "expand_with_row",
    "run_with_dataset", "DataDrivenError",
    "HealingError", "HealingRegistry", "healing_registry",
    "register_fallback", "register_fallbacks", "clear_fallbacks",
    "find_with_healing_selenium", "find_with_healing_playwright",
    "http_request", "http_get", "http_post", "http_put", "http_patch", "http_delete",
    "http_assert_status", "http_assert_json_contains", "get_last_response",
    "HttpAssertionError",
    "AccessibilityError", "load_axe_source", "selenium_run_audit",
    "playwright_run_audit", "summarise_violations",
    "CDPError", "selenium_cdp", "playwright_cdp", "reset_playwright_cdp_sessions",
    "CDPEventListener", "CDPEventLoopError", "resolve_cdp_ws_url",
    "TracingError", "record_trace",
    "BidiNetworkError",
    "bidi_add_request_handler", "bidi_add_response_handler",
    "bidi_add_auth_handler", "bidi_clear_network_handlers",
    "summarise_run", "notify_webhook", "notify_slack", "notify_run_summary",
    "NotifierError",
    "POMGeneratorError", "extract_elements_from_html", "generate_pom_class",
    "generate_pom_from_html", "generate_pom_from_url", "write_pom_to_file",
    "validate_action_json", "validate_action_file", "validate_action_files",
    "visual_capture_baseline", "visual_compare_with_baseline",
    "recorder_start", "recorder_stop", "recorder_pull_events",
    "recorder_events_to_actions", "recorder_save_recording",
    "PlaywrightBackendError", "PlaywrightWrapper", "playwright_wrapper_instance",
    "PlaywrightElementWrapper", "playwright_element_wrapper",
    "pw_launch", "pw_quit", "pw_start_har_recording", "pw_stop_har_recording",
    "pw_route_mock", "pw_route_mock_json", "pw_route_unmock", "pw_route_clear",
    "pw_to_url", "pw_forward", "pw_back", "pw_refresh",
    "pw_url", "pw_title", "pw_content",
    "pw_set_default_timeout", "pw_set_default_navigation_timeout",
    "pw_new_page", "pw_switch_to_page", "pw_close_page", "pw_page_count",
    "pw_find_element", "pw_find_elements",
    "pw_find_element_with_test_object_record", "pw_find_elements_with_test_object_record",
    "pw_save_test_object_to_selector",
    "pw_click", "pw_dblclick", "pw_hover",
    "pw_fill", "pw_type_text", "pw_press",
    "pw_check", "pw_uncheck", "pw_select_option", "pw_drag_and_drop",
    "pw_evaluate",
    "pw_get_cookies", "pw_add_cookies", "pw_clear_cookies",
    "pw_screenshot", "pw_screenshot_bytes",
    "pw_wait_for_selector", "pw_wait_for_load_state",
    "pw_wait_for_timeout", "pw_wait_for_url",
    "pw_set_viewport_size", "pw_viewport_size",
    "pw_mouse_click", "pw_mouse_move", "pw_mouse_down", "pw_mouse_up",
    "pw_keyboard_press", "pw_keyboard_type", "pw_keyboard_down", "pw_keyboard_up",
    # Phase 1: chrome_profile
    "ChromeProfileError", "StealthFlags",
    "chrome_profile_build_options", "build_playwright_persistent_context",
    "build_stealth_chrome_driver", "chrome_profile_session",
    "cleanup_chrome_locks", "minimise_chrome_windows",
    "snapshot_chrome_profile", "sync_chrome_profile_back",
    # Phase 2: failure_triage
    "FailureTriageError", "TriageReport", "TriageSignals",
    "extract_signals_from_bundle", "triage_render_markdown",
    "triage_save_report", "triage_bundle", "triage_failure",
    # Phase 3: flake_detector
    "FlakeDetectorError", "FlakeScore", "QuarantineEntry", "QuarantineRegistry",
    "compute_flake_scores", "flake_detector_flaky_paths", "flaky_quarantine",
    "quarantine_flaky", "quarantine_report_markdown", "release_if_stable",
    # Phase 4: locator_health
    "FallbackHitTracker", "LocatorFinding", "LocatorHealthError",
    "LocatorHealthReport", "LocatorUpgradeSuggestion",
    "locator_apply_upgrades", "locator_build_health_report",
    "fallback_hit_tracker", "locator_render_health_markdown",
    "save_health_report", "locator_scan_action_file", "locator_scan_project",
    "locator_suggest_upgrade", "locator_suggest_upgrades",
    # Phase 5: device_cloud
    "CloudCredentials", "CloudSession", "DeviceCloudError", "RealDeviceCaps",
    "device_cloud_build_capabilities", "connect_real_device",
    "fetch_session_info", "device_cloud_load_credentials",
    "session_summary_markdown", "update_session_status",
    # Phase 6: otel_bridge
    "TraceBridgeError", "TraceContext",
    "bridged_span_playwright", "bridged_span_selenium",
    "clear_headers_playwright", "clear_headers_selenium",
    "current_otel_context", "inject_headers_playwright",
    "inject_headers_selenium", "parse_traceparent",
    "random_trace_context", "trace_link",
    # Phase 7: mutation_testing
    "Mutation", "MutationResult", "MutationScore", "MutationTestingError",
    "MutationType", "apply_mutation", "mutation_assert_min_score",
    "generate_mutations", "render_mutation_markdown",
    "run_mutation_testing", "run_mutation_testing_on_file",
    # Phase 8: otp_interceptor
    "ImapProvider", "OtpInMemoryProvider", "InterceptedMessage",
    "MailHogProvider", "MailpitProvider", "OtpInterceptError",
    "OtpProvider", "WebhookSmsProvider",
    "extract_otp_from_text", "wait_for_otp",
    # Phase 9: download_verify
    "DownloadAssertion", "DownloadVerifyError",
    "assert_csv_columns", "assert_csv_row_count", "assert_download",
    "assert_file_sha256", "assert_json_matches_schema",
    "assert_pdf_contains", "assert_pdf_matches",
    "extract_pdf_text", "read_csv_rows", "read_excel_rows",
    "read_json_file", "sha256_of_file", "wait_for_download",
    # Phase 11: test_auto_repair
    "RepairPlan", "TestAutoRepairError",
    "apply_repair", "collect_git_diff", "propose_repair",
    "render_repair_markdown", "repair_from_bundle",
    # Phase 12: edge_case_generator
    "EdgeCase", "EdgeCaseCategory", "EdgeCaseGeneratorError",
    "EdgeCaseSuite",
    "generate_edge_cases", "generate_edge_cases_from_file",
    "edge_case_render_markdown", "edge_case_write_suite",
    # Phase 13: openapi_to_e2e
    "OpenAPIGeneratedTest", "OpenAPIGenerationResult",
    "OpenAPIGeneratorError",
    "openapi_generate_from_file", "openapi_generate_from_spec",
    "openapi_load_spec", "openapi_synthesize_example", "openapi_write_tests",
    # Phase 14: cross_tab_sync
    "CrossTabSyncError", "PropagationResult",
    "assert_state_propagates", "broadcast_message",
    "collect_broadcast_messages", "get_storage_value",
    "install_broadcast_recorder", "post_message_to_page",
    "set_storage_value", "wait_for_broadcast", "wait_for_storage",
    # Phase 15: visual_ai
    "VisualHashResult", "VisualSimilarityResult", "VisualAIError",
    "assert_visual_similar",
    "visual_average_hash", "visual_compare_images",
    "visual_difference_hash", "visual_hamming_distance",
    "visual_hash_similarity", "visual_perceptual_hash",
    # Phase 16: test_scheduler
    "Schedule", "TestCandidate", "TestSchedulerError",
    "build_candidates_from_ledger", "render_schedule_markdown",
    "schedule_tests",
    "scheduler_value_density", "scheduler_value_of",
    # Phase 17: walkthrough_docs
    "Walkthrough", "WalkthroughError", "WalkthroughStep",
    "build_walkthrough",
    "walkthrough_collect_steps", "walkthrough_narrate_steps",
    "walkthrough_render_confluence", "walkthrough_render_markdown",
    "save_walkthrough",
    # Phase 19: live_dashboard
    "DashboardConfig", "DashboardServer", "LiveDashboardError",
    "dashboard_build_summary",
]
