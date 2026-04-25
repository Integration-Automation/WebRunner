import builtins
import time
import types
from datetime import datetime
from inspect import getmembers, isbuiltin
from pathlib import Path
from typing import Optional, Union

# 禁止暴露於 JSON 動作執行器的內建函式，避免任意程式碼執行
# Builtins that must never be callable from user-supplied JSON actions,
# per CLAUDE.md: "Action executor must only call registered commands;
# never use eval()/exec() on user input."
_UNSAFE_BUILTINS = frozenset({
    "eval", "exec", "compile", "__import__", "__build_class__",
    "open", "input", "breakpoint",
    "globals", "locals", "vars",
    "getattr", "setattr", "delattr",
})

# WR_* 命令會把整段 JavaScript 字串送進瀏覽器執行；當 action JSON 來源不可信時
# 必須能關閉。透過 ``set_allow_arbitrary_script(False)`` 切換。
# WR_* commands that hand a JS string straight to the browser. When action
# JSON comes from an untrusted source the operator should be able to disable
# them; ``set_allow_arbitrary_script(False)`` flips the gate.
_ARBITRARY_SCRIPT_COMMANDS = frozenset({
    "WR_execute_script",
    "WR_execute_async_script",
    "WR_pw_evaluate",
    "WR_cdp",
    "WR_pw_cdp",
})

from je_web_runner.manager.webrunner_manager import web_runner
from je_web_runner.utils.exception.exception_tags import add_command_exception_tag
from je_web_runner.utils.exception.exception_tags import executor_data_error, executor_list_error
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException, WebRunnerAddCommandException
from je_web_runner.utils.generate_report.generate_html_report import generate_html
from je_web_runner.utils.generate_report.generate_html_report import generate_html_report
from je_web_runner.utils.generate_report.generate_json_report import generate_json
from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml_report
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
from je_web_runner.utils.generate_report.generate_allure_report import generate_allure
from je_web_runner.utils.generate_report.generate_allure_report import generate_allure_report
from je_web_runner.utils.json.json_file.json_file import read_action_json
from je_web_runner.utils.accessibility.axe_audit import (
    load_axe_source as _axe_load_source,
    playwright_run_audit as _axe_run_pw,
    selenium_run_audit as _axe_run_selenium,
    summarise_violations as _axe_summarise,
)
from je_web_runner.utils.observability import event_capture as _event_capture
from je_web_runner.utils.secrets_scanner import scanner as _secrets
from je_web_runner.utils.security_headers import headers_audit as _headers_audit
from je_web_runner.utils.perf_metrics import page_metrics as _perf
from je_web_runner.utils.snapshot import snapshot as _snapshot
from je_web_runner.utils.har_diff import har_diff as _har_diff
from je_web_runner.utils.test_filter import dependency as _dependency
from je_web_runner.utils.test_filter import tag_filter as _tag_filter
from je_web_runner.utils.ab_run import ab_runner as _ab
from je_web_runner.utils.cloud_grid import cloud_drivers as _cloud
from je_web_runner.utils.ci_annotations import github_annotations as _gh_annotations
from je_web_runner.utils.lighthouse import lighthouse_runner as _lighthouse
from je_web_runner.utils.load_test import locust_wrapper as _locust
from je_web_runner.utils.test_management import jira_client as _jira
from je_web_runner.utils.test_management import testrail_client as _testrail
from je_web_runner.utils.run_ledger import flaky as _flaky
from je_web_runner.utils.run_ledger import ledger as _ledger
from je_web_runner.utils.service_worker import sw_control as _sw
from je_web_runner.utils.storage import browser_storage as _storage
from je_web_runner.utils.cdp.cdp_commands import (
    playwright_cdp as _cdp_playwright,
    reset_playwright_cdp_sessions as _cdp_reset,
    selenium_cdp as _cdp_selenium,
)
from je_web_runner.utils.api.http_client import (
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
    expand_with_row,
    load_dataset_csv,
    load_dataset_json,
    run_with_dataset,
)
from je_web_runner.utils.env_config.env_loader import expand_in_action, get_env, load_env
from je_web_runner.utils.pom_generator.pom_generator import (
    generate_pom_from_html,
    generate_pom_from_url,
    write_pom_to_file,
)
from je_web_runner.utils.notifier.webhook_notifier import (
    notify_run_summary,
    notify_slack,
    notify_webhook,
    summarise_run,
)
from je_web_runner.utils.self_healing.healing_locator import (
    clear_fallbacks as _heal_clear_fallbacks,
    find_with_healing_playwright as _heal_find_pw,
    find_with_healing_selenium as _heal_find_selenium,
    register_fallback as _heal_register_fallback,
    register_fallbacks as _heal_register_fallbacks,
)
from je_web_runner.utils.json.json_validator import validate_action_file, validate_action_json
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.package_manager.package_manager_class import package_manager
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.visual_regression.visual_diff import capture_baseline as _visual_capture_baseline
from je_web_runner.utils.visual_regression.visual_diff import compare_with_baseline as _visual_compare
from je_web_runner.webdriver import playwright_wrapper as _pw
from je_web_runner.webdriver.playwright_element_wrapper import playwright_element_wrapper as _pw_element
from je_web_runner.utils.recorder.browser_recorder import pull_events as _recorder_pull_events
from je_web_runner.utils.recorder.browser_recorder import save_recording as _recorder_save_recording
from je_web_runner.utils.recorder.browser_recorder import start_recording as _recorder_start
from je_web_runner.utils.recorder.browser_recorder import stop_recording as _recorder_stop
from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


def _try_selenium_screenshot() -> Optional[bytes]:
    try:
        if webdriver_wrapper_instance.current_webdriver is None:
            return None
        return webdriver_wrapper_instance.get_screenshot_as_png()
    except Exception:  # noqa: BLE001 — best-effort fallback path
        return None


def _try_playwright_screenshot() -> Optional[bytes]:
    try:
        if not _pw.playwright_wrapper_instance._pages:
            return None
        return _pw.playwright_wrapper_instance.screenshot_bytes()
    except Exception:  # noqa: BLE001 — best-effort fallback path
        return None


class Executor(object):

    def __init__(self):
        # 失敗時自動截圖目錄；None 代表停用
        # Output directory for auto-captured failure screenshots; None disables it.
        self.failure_screenshot_dir: Optional[str] = None
        # 全域重試策略 (預設關閉)
        # Global retry policy. retries == 0 disables retry; backoff is in
        # seconds and is multiplied by the (1-based) attempt number.
        self.retry_policy = {"retries": 0, "backoff": 0.0}
        # 是否允許將任意 JS / CDP 字串透過 action 送到瀏覽器；預設 True 維持向下
        # 相容，但若 action JSON 來自不可信來源請改 False。
        # Default True for back-compat; flip to False when action JSON comes
        # from an untrusted source.
        self.allow_arbitrary_script: bool = True
        # 事件字典：將字串名稱對應到實際可執行的函式
        # Event dictionary: map string keys to actual callable functions
        self.event_dict = {
            # webdriver manager
            "WR_get_webdriver_manager": web_runner.new_driver,
            "WR_change_index_of_webdriver": web_runner.change_webdriver,
            "WR_quit": web_runner.quit,

            # test object
            "WR_SaveTestObject": test_object_record.save_test_object,
            "WR_CleanTestObject": test_object_record.clean_record,

            # webdriver wrapper
            "WR_set_driver": webdriver_wrapper_instance.set_driver,
            "WR_set_webdriver_options_capability": webdriver_wrapper_instance.set_webdriver_options_capability,
            "WR_find_element": webdriver_wrapper_instance.find_element_with_test_object_record,
            "WR_find_elements": webdriver_wrapper_instance.find_elements_with_test_object_record,
            "WR_implicitly_wait": webdriver_wrapper_instance.implicitly_wait,
            "WR_explict_wait": webdriver_wrapper_instance.explict_wait,
            "WR_to_url": webdriver_wrapper_instance.to_url,
            "WR_forward": webdriver_wrapper_instance.forward,
            "WR_back": webdriver_wrapper_instance.back,
            "WR_refresh": webdriver_wrapper_instance.refresh,
            "WR_switch": webdriver_wrapper_instance.switch,
            "WR_set_script_timeout": webdriver_wrapper_instance.set_script_timeout,
            "WR_set_page_load_timeout": webdriver_wrapper_instance.set_page_load_timeout,
            "WR_get_cookies": webdriver_wrapper_instance.get_cookies,
            "WR_get_cookie": webdriver_wrapper_instance.get_cookie,
            "WR_add_cookie": webdriver_wrapper_instance.add_cookie,
            "WR_delete_cookie": webdriver_wrapper_instance.delete_cookie,
            "WR_delete_all_cookies": webdriver_wrapper_instance.delete_all_cookies,
            "WR_execute": webdriver_wrapper_instance.execute,
            "WR_execute_script": webdriver_wrapper_instance.execute_script,
            "WR_execute_async_script": webdriver_wrapper_instance.execute_async_script,
            "WR_move_to_element": webdriver_wrapper_instance.move_to_element_with_test_object,
            "WR_move_to_element_with_offset": webdriver_wrapper_instance.move_to_element_with_offset_and_test_object,
            "WR_drag_and_drop": webdriver_wrapper_instance.drag_and_drop_with_test_object,
            "WR_drag_and_drop_offset": webdriver_wrapper_instance.drag_and_drop_offset_with_test_object,
            "WR_perform": webdriver_wrapper_instance.perform,
            "WR_reset_actions": webdriver_wrapper_instance.reset_actions,
            "WR_left_click": webdriver_wrapper_instance.left_click_with_test_object,
            "WR_left_click_and_hold": webdriver_wrapper_instance.left_click_and_hold_with_test_object,
            "WR_right_click": webdriver_wrapper_instance.right_click_with_test_object,
            "WR_left_double_click": webdriver_wrapper_instance.left_double_click_with_test_object,
            "WR_release": webdriver_wrapper_instance.release_with_test_object,
            "WR_press_key": webdriver_wrapper_instance.press_key_with_test_object,
            "WR_release_key": webdriver_wrapper_instance.release_key_with_test_object,
            "WR_move_by_offset": webdriver_wrapper_instance.move_by_offset,
            "WR_pause": webdriver_wrapper_instance.pause,
            "WR_send_keys": webdriver_wrapper_instance.send_keys,
            "WR_send_keys_to_element": webdriver_wrapper_instance.send_keys_to_element_with_test_object,
            "WR_scroll": webdriver_wrapper_instance.scroll,
            "WR_check_current_webdriver": webdriver_wrapper_instance.check_current_webdriver,
            "WR_maximize_window": webdriver_wrapper_instance.maximize_window,
            "WR_fullscreen_window": webdriver_wrapper_instance.fullscreen_window,
            "WR_minimize_window": webdriver_wrapper_instance.minimize_window,
            "WR_set_window_size": webdriver_wrapper_instance.set_window_size,
            "WR_set_window_position": webdriver_wrapper_instance.set_window_position,
            "WR_get_window_position": webdriver_wrapper_instance.get_window_position,
            "WR_get_window_rect": webdriver_wrapper_instance.get_window_rect,
            "WR_set_window_rect": webdriver_wrapper_instance.set_window_rect,
            "WR_get_screenshot_as_png": webdriver_wrapper_instance.get_screenshot_as_png,
            "WR_get_screenshot_as_base64": webdriver_wrapper_instance.get_screenshot_as_base64,
            "WR_get_log": webdriver_wrapper_instance.get_log,
            "WR_single_quit": webdriver_wrapper_instance.quit,

            # web element
            "WR_element_submit": web_runner.webdriver_element.submit,
            "WR_element_clear": web_runner.webdriver_element.clear,
            "WR_element_get_property": web_runner.webdriver_element.get_property,
            "WR_element_get_dom_attribute": web_runner.webdriver_element.get_dom_attribute,
            "WR_element_get_attribute": web_runner.webdriver_element.get_attribute,
            "WR_element_is_selected": web_runner.webdriver_element.is_selected,
            "WR_element_is_enabled": web_runner.webdriver_element.is_enabled,
            "WR_input_to_element": web_runner.webdriver_element.input_to_element,
            "WR_click_element": web_runner.webdriver_element.click_element,
            "WR_element_is_displayed": web_runner.webdriver_element.is_displayed,
            "WR_element_value_of_css_property": web_runner.webdriver_element.value_of_css_property,
            "WR_element_screenshot": web_runner.webdriver_element.screenshot,
            "WR_element_change_web_element": web_runner.webdriver_element.change_web_element,
            "WR_element_check_current_web_element": web_runner.webdriver_element.check_current_web_element,
            "WR_element_get_select": web_runner.webdriver_element.get_select,

            # init test record
            "WR_set_record_enable": test_record_instance.set_record_enable,

            # generate report
            "WR_generate_html": generate_html,
            "WR_generate_html_report": generate_html_report,
            "WR_generate_json": generate_json,
            "WR_generate_json_report": generate_json_report,
            "WR_generate_xml": generate_xml,
            "WR_generate_xml_report": generate_xml_report,
            "WR_generate_junit_xml": generate_junit_xml,
            "WR_generate_junit_xml_report": generate_junit_xml_report,
            "WR_generate_allure": generate_allure,
            "WR_generate_allure_report": generate_allure_report,

            # execute
            "WR_execute_action": self.execute_action,
            "WR_execute_files": self.execute_files,

            # validate
            "WR_validate_action_json": validate_action_json,
            "WR_validate_action_file": validate_action_file,

            # environment configuration
            "WR_load_env": load_env,
            "WR_get_env": get_env,
            "WR_expand_env_in_action": expand_in_action,

            # data-driven testing
            "WR_load_dataset_csv": load_dataset_csv,
            "WR_load_dataset_json": load_dataset_json,
            "WR_expand_with_row": expand_with_row,
            "WR_run_with_dataset": lambda action_data, rows: run_with_dataset(
                action_data, rows, self.execute_action
            ),

            # failure auto-screenshot
            "WR_set_failure_screenshot_dir": self.set_failure_screenshot_dir,

            # retry policy
            "WR_set_retry_policy": self.set_retry_policy,

            # security: arbitrary-script gate
            "WR_set_allow_arbitrary_script": self.set_allow_arbitrary_script,

            # self-healing locators
            "WR_register_fallback_locator": _heal_register_fallback,
            "WR_register_fallback_locators": _heal_register_fallbacks,
            "WR_clear_fallback_locators": _heal_clear_fallbacks,
            "WR_find_with_healing": _heal_find_selenium,
            "WR_pw_find_with_healing": _heal_find_pw,

            # HTTP API testing
            "WR_http_request": http_request,
            "WR_http_get": http_get,
            "WR_http_post": http_post,
            "WR_http_put": http_put,
            "WR_http_patch": http_patch,
            "WR_http_delete": http_delete,
            "WR_http_assert_status": http_assert_status,
            "WR_http_assert_json_contains": http_assert_json_contains,

            # raw CDP
            "WR_cdp": _cdp_selenium,
            "WR_pw_cdp": _cdp_playwright,
            "WR_pw_cdp_reset_sessions": _cdp_reset,

            # storage (Selenium)
            "WR_local_storage_set": _storage.selenium_local_storage_set,
            "WR_local_storage_get": _storage.selenium_local_storage_get,
            "WR_local_storage_remove": _storage.selenium_local_storage_remove,
            "WR_local_storage_clear": _storage.selenium_local_storage_clear,
            "WR_local_storage_all": _storage.selenium_local_storage_all,
            "WR_session_storage_set": _storage.selenium_session_storage_set,
            "WR_session_storage_get": _storage.selenium_session_storage_get,
            "WR_session_storage_clear": _storage.selenium_session_storage_clear,
            "WR_indexed_db_drop": _storage.selenium_indexed_db_drop,
            # storage (Playwright)
            "WR_pw_local_storage_set": _storage.playwright_local_storage_set,
            "WR_pw_local_storage_get": _storage.playwright_local_storage_get,
            "WR_pw_local_storage_remove": _storage.playwright_local_storage_remove,
            "WR_pw_local_storage_clear": _storage.playwright_local_storage_clear,
            "WR_pw_local_storage_all": _storage.playwright_local_storage_all,
            "WR_pw_session_storage_set": _storage.playwright_session_storage_set,
            "WR_pw_session_storage_get": _storage.playwright_session_storage_get,
            "WR_pw_session_storage_clear": _storage.playwright_session_storage_clear,
            "WR_pw_indexed_db_drop": _storage.playwright_indexed_db_drop,

            # service worker / cache storage
            "WR_sw_unregister": _sw.selenium_unregister_service_workers,
            "WR_sw_clear_caches": _sw.selenium_clear_caches,
            "WR_sw_bypass": _sw.selenium_bypass_service_worker,
            "WR_pw_sw_unregister": _sw.playwright_unregister_service_workers,
            "WR_pw_sw_clear_caches": _sw.playwright_clear_caches,
            "WR_pw_sw_bypass": _sw.playwright_bypass_service_worker,

            # console / network event capture
            "WR_pw_event_capture_start": _event_capture.start_event_capture,
            "WR_pw_event_capture_stop": _event_capture.stop_event_capture,
            "WR_pw_event_capture_clear": _event_capture.clear_event_capture,
            "WR_pw_console_messages": _event_capture.get_console_messages,
            "WR_pw_network_responses": _event_capture.get_network_responses,
            "WR_pw_assert_no_console_errors": _event_capture.assert_no_console_errors,
            "WR_pw_assert_no_5xx": _event_capture.assert_no_5xx,
            "WR_pw_assert_no_4xx_or_5xx": _event_capture.assert_no_4xx_or_5xx,

            # secrets scanner
            "WR_scan_secrets": _secrets.scan_action,
            "WR_scan_secrets_file": _secrets.scan_action_file,
            "WR_assert_no_secrets": _secrets.assert_no_secrets,

            # security headers audit
            "WR_audit_security_headers": _headers_audit.audit_headers,
            "WR_audit_security_headers_url": _headers_audit.audit_url,

            # page perf metrics
            "WR_perf_collect": _perf.selenium_collect_metrics,
            "WR_pw_perf_collect": _perf.playwright_collect_metrics,
            "WR_perf_assert_within": _perf.assert_metrics_within,

            # snapshot testing
            "WR_match_snapshot": _snapshot.match_snapshot,
            "WR_update_snapshot": _snapshot.update_snapshot,
            "WR_delete_snapshot": _snapshot.delete_snapshot,

            # HAR diff
            "WR_diff_har": _har_diff.diff_har,
            "WR_diff_har_files": _har_diff.diff_har_files,

            # tag filter / dependencies
            "WR_read_metadata": _tag_filter.read_metadata,
            "WR_filter_paths": _tag_filter.filter_paths,
            "WR_read_depends_on": _dependency.read_depends_on,
            "WR_build_dependency_graph": _dependency.build_dependency_graph,
            "WR_topological_order": _dependency.topological_order,
            "WR_skip_dependents_of_failed": _dependency.skip_dependents_of_failed,

            # run ledger
            "WR_ledger_record_run": _ledger.record_run,
            "WR_ledger_failed_files": _ledger.failed_files,
            "WR_ledger_passed_files": _ledger.passed_files,
            "WR_ledger_clear": _ledger.clear_ledger,
            "WR_flakiness_stats": _flaky.flakiness_stats,
            "WR_flaky_paths": _flaky.flaky_paths,

            # A/B run mode
            "WR_run_ab": _ab.run_ab,
            "WR_diff_ab_records": _ab.diff_records,

            # cloud grid (BrowserStack / Sauce Labs / LambdaTest)
            "WR_browserstack_capabilities": _cloud.build_browserstack_capabilities,
            "WR_saucelabs_capabilities": _cloud.build_saucelabs_capabilities,
            "WR_lambdatest_capabilities": _cloud.build_lambdatest_capabilities,
            "WR_connect_browserstack": _cloud.connect_browserstack,
            "WR_connect_saucelabs": _cloud.connect_saucelabs,
            "WR_connect_lambdatest": _cloud.connect_lambdatest,
            "WR_start_remote_driver": _cloud.start_remote_driver,

            # JIRA / TestRail integration
            "WR_jira_create_issue": _jira.jira_create_issue,
            "WR_jira_create_failure_issues": _jira.jira_create_failure_issues,
            "WR_testrail_send_results": _testrail.testrail_send_results,
            "WR_testrail_results_from_pairs": _testrail.testrail_results_from_pairs,
            "WR_testrail_close_run": _testrail.testrail_close_run,

            # GitHub Actions annotations
            "WR_gh_format_error": _gh_annotations.format_error_annotation,
            "WR_gh_emit_failures": _gh_annotations.emit_failure_annotations,
            "WR_gh_emit_from_junit_xml": _gh_annotations.emit_from_junit_xml,

            # Lighthouse
            "WR_lighthouse_run": _lighthouse.run_lighthouse,
            "WR_lighthouse_assert_scores": _lighthouse.assert_scores,

            # Locust load testing
            "WR_locust_run": _locust.run_locust,
            "WR_locust_build_user_class": _locust.build_http_user_class,

            # accessibility (axe-core)
            "WR_a11y_load_axe": _axe_load_source,
            "WR_a11y_run_audit": _axe_run_selenium,
            "WR_pw_a11y_run_audit": _axe_run_pw,
            "WR_a11y_summarise": _axe_summarise,

            # webhook / Slack notifications
            "WR_summarise_run": summarise_run,
            "WR_notify_webhook": notify_webhook,
            "WR_notify_slack": notify_slack,
            "WR_notify_run_summary": notify_run_summary,

            # page-object model generator
            "WR_generate_pom_from_url": generate_pom_from_url,
            "WR_generate_pom_from_html": generate_pom_from_html,
            "WR_write_pom_to_file": write_pom_to_file,

            # visual regression
            "WR_visual_capture_baseline": _visual_capture_baseline,
            "WR_visual_compare": _visual_compare,

            # browser recorder (auto-binds to webdriver_wrapper_instance)
            "WR_recorder_start": lambda: _recorder_start(webdriver_wrapper_instance),
            "WR_recorder_stop": lambda: _recorder_stop(webdriver_wrapper_instance),
            "WR_recorder_pull_events": lambda: _recorder_pull_events(webdriver_wrapper_instance),
            "WR_recorder_save": lambda output_path, raw_events_path=None: _recorder_save_recording(
                webdriver_wrapper_instance, output_path, raw_events_path
            ),

            # playwright backend — page-level operations
            "WR_pw_launch": _pw.pw_launch,
            "WR_pw_quit": _pw.pw_quit,
            "WR_pw_start_har_recording": _pw.pw_start_har_recording,
            "WR_pw_stop_har_recording": _pw.pw_stop_har_recording,
            # network route mocking
            "WR_pw_route_mock": _pw.pw_route_mock,
            "WR_pw_route_mock_json": _pw.pw_route_mock_json,
            "WR_pw_route_unmock": _pw.pw_route_unmock,
            "WR_pw_route_clear": _pw.pw_route_clear,
            # device emulation
            "WR_pw_emulate": _pw.pw_emulate,
            "WR_pw_stop_emulate": _pw.pw_stop_emulate,
            "WR_pw_list_devices": _pw.pw_list_devices,
            # geolocation / permissions / timezone / clock
            "WR_pw_set_geolocation": _pw.pw_set_geolocation,
            "WR_pw_grant_permissions": _pw.pw_grant_permissions,
            "WR_pw_clear_permissions": _pw.pw_clear_permissions,
            "WR_pw_set_timezone": _pw.pw_set_timezone,
            "WR_pw_clock_install": _pw.pw_clock_install,
            "WR_pw_clock_set_time": _pw.pw_clock_set_time,
            "WR_pw_clock_run_for": _pw.pw_clock_run_for,
            "WR_pw_set_locale": _pw.pw_set_locale,
            "WR_pw_to_url": _pw.pw_to_url,
            "WR_pw_forward": _pw.pw_forward,
            "WR_pw_back": _pw.pw_back,
            "WR_pw_refresh": _pw.pw_refresh,
            "WR_pw_url": _pw.pw_url,
            "WR_pw_title": _pw.pw_title,
            "WR_pw_content": _pw.pw_content,
            "WR_pw_set_default_timeout": _pw.pw_set_default_timeout,
            "WR_pw_set_default_navigation_timeout": _pw.pw_set_default_navigation_timeout,
            # pages / tabs
            "WR_pw_new_page": _pw.pw_new_page,
            "WR_pw_switch_to_page": _pw.pw_switch_to_page,
            "WR_pw_close_page": _pw.pw_close_page,
            "WR_pw_page_count": _pw.pw_page_count,
            # finding
            "WR_pw_find_element": _pw.pw_find_element,
            "WR_pw_find_elements": _pw.pw_find_elements,
            "WR_pw_find_element_with_test_object_record": _pw.pw_find_element_with_test_object_record,
            "WR_pw_find_elements_with_test_object_record": _pw.pw_find_elements_with_test_object_record,
            "WR_pw_save_test_object_to_selector": _pw.pw_save_test_object_to_selector,
            # direct page-level shortcuts
            "WR_pw_click": _pw.pw_click,
            "WR_pw_dblclick": _pw.pw_dblclick,
            "WR_pw_hover": _pw.pw_hover,
            "WR_pw_fill": _pw.pw_fill,
            "WR_pw_type_text": _pw.pw_type_text,
            "WR_pw_press": _pw.pw_press,
            "WR_pw_check": _pw.pw_check,
            "WR_pw_uncheck": _pw.pw_uncheck,
            "WR_pw_select_option": _pw.pw_select_option,
            "WR_pw_drag_and_drop": _pw.pw_drag_and_drop,
            # script
            "WR_pw_evaluate": _pw.pw_evaluate,
            # cookies
            "WR_pw_get_cookies": _pw.pw_get_cookies,
            "WR_pw_add_cookies": _pw.pw_add_cookies,
            "WR_pw_clear_cookies": _pw.pw_clear_cookies,
            # screenshots
            "WR_pw_screenshot": _pw.pw_screenshot,
            "WR_pw_screenshot_bytes": _pw.pw_screenshot_bytes,
            # waits
            "WR_pw_wait_for_selector": _pw.pw_wait_for_selector,
            "WR_pw_wait_for_load_state": _pw.pw_wait_for_load_state,
            "WR_pw_wait_for_timeout": _pw.pw_wait_for_timeout,
            "WR_pw_wait_for_url": _pw.pw_wait_for_url,
            # viewport
            "WR_pw_set_viewport_size": _pw.pw_set_viewport_size,
            "WR_pw_viewport_size": _pw.pw_viewport_size,
            # mouse / keyboard
            "WR_pw_mouse_click": _pw.pw_mouse_click,
            "WR_pw_mouse_move": _pw.pw_mouse_move,
            "WR_pw_mouse_down": _pw.pw_mouse_down,
            "WR_pw_mouse_up": _pw.pw_mouse_up,
            "WR_pw_keyboard_press": _pw.pw_keyboard_press,
            "WR_pw_keyboard_type": _pw.pw_keyboard_type,
            "WR_pw_keyboard_down": _pw.pw_keyboard_down,
            "WR_pw_keyboard_up": _pw.pw_keyboard_up,
            # element-level (operates on captured current element)
            "WR_pw_element_click": _pw_element.click,
            "WR_pw_element_dblclick": _pw_element.dblclick,
            "WR_pw_element_hover": _pw_element.hover,
            "WR_pw_element_fill": _pw_element.fill,
            "WR_pw_element_type_text": _pw_element.type_text,
            "WR_pw_element_press": _pw_element.press,
            "WR_pw_element_clear": _pw_element.clear,
            "WR_pw_element_check": _pw_element.check,
            "WR_pw_element_uncheck": _pw_element.uncheck,
            "WR_pw_element_select_option": _pw_element.select_option,
            "WR_pw_element_get_attribute": _pw_element.get_attribute,
            "WR_pw_element_get_property": _pw_element.get_property,
            "WR_pw_element_inner_text": _pw_element.inner_text,
            "WR_pw_element_inner_html": _pw_element.inner_html,
            "WR_pw_element_is_visible": _pw_element.is_visible,
            "WR_pw_element_is_enabled": _pw_element.is_enabled,
            "WR_pw_element_is_checked": _pw_element.is_checked,
            "WR_pw_element_scroll_into_view": _pw_element.scroll_into_view,
            "WR_pw_element_screenshot": _pw_element.screenshot,
            "WR_pw_element_change": _pw_element.change_element,

            # Add package
            "WR_add_package_to_executor": package_manager.add_package_to_executor,
            "WR_add_package_to_callback_executor": package_manager.add_package_to_callback_executor,

            # ----- naming aliases (clearer / consistent names) ------------
            # Legacy names above are kept for back-compat; prefer these.
            "WR_new_driver": web_runner.new_driver,                              # alias of WR_get_webdriver_manager
            "WR_quit_all": web_runner.quit,                                       # alias of WR_quit
            "WR_quit_current": webdriver_wrapper_instance.quit,                   # alias of WR_single_quit
            "WR_explicit_wait": webdriver_wrapper_instance.explict_wait,          # fixes "explict" typo
            "WR_save_test_object": test_object_record.save_test_object,           # snake_case form of WR_SaveTestObject
            "WR_clear_test_objects": test_object_record.clean_record,             # accurate verb vs "Clean"
            "WR_find_recorded_element": webdriver_wrapper_instance.find_element_with_test_object_record,
            "WR_find_recorded_elements": webdriver_wrapper_instance.find_elements_with_test_object_record,
            "WR_element_input": web_runner.webdriver_element.input_to_element,    # WR_element_* prefix
            "WR_element_click": web_runner.webdriver_element.click_element,       # WR_element_* prefix
            "WR_element_assert": web_runner.webdriver_element.check_current_web_element,

            # ----- usable Select wrappers (replaces unreachable WR_element_get_select) -----
            "WR_element_select_by_value": web_runner.webdriver_element.select_by_value,
            "WR_element_select_by_index": web_runner.webdriver_element.select_by_index,
            "WR_element_select_by_visible_text": web_runner.webdriver_element.select_by_visible_text,
        }

        # 將安全的 Python 內建函式加入事件字典，過濾可執行任意程式碼者
        # Register safe Python builtins only; skip those that enable arbitrary
        # code execution or unrestricted I/O.
        for name, function in getmembers(builtins, isbuiltin):
            if name in _UNSAFE_BUILTINS:
                continue
            self.event_dict[name] = function

    def set_retry_policy(self, retries: int = 0, backoff: float = 0.0) -> None:
        """
        設定全域重試策略
        Configure the global retry policy. ``retries`` is the number of extra
        attempts after the first; ``backoff`` is base seconds between attempts
        (multiplied by the attempt index, so 0.5 → 0.5s, 1.0s, 1.5s …).
        """
        self.retry_policy = {"retries": max(int(retries), 0), "backoff": max(float(backoff), 0.0)}

    def _execute_with_retry(self, action):
        """Run ``_execute_event`` honouring the global retry policy."""
        retries = int(self.retry_policy.get("retries", 0))
        backoff = float(self.retry_policy.get("backoff", 0.0))
        for attempt in range(retries + 1):
            try:
                return self._execute_event(action)
            except Exception as error:  # noqa: BLE001 — retry layer must catch all
                if attempt >= retries:
                    raise
                if backoff > 0:
                    time.sleep(backoff * (attempt + 1))
                web_runner_logger.warning(
                    f"action {action!r} failed on attempt {attempt + 1}, retrying: {error!r}"
                )
        # Unreachable: ``range(retries + 1)`` always has at least one iteration.
        raise WebRunnerExecuteException("retry loop exited without resolution")

    def set_failure_screenshot_dir(self, path: Optional[str]) -> None:
        """
        設定 (或停用) 動作失敗時的自動截圖目錄
        Configure the directory used for auto-screenshots on action failure.
        Pass ``None`` to disable.
        """
        if path:
            Path(path).mkdir(parents=True, exist_ok=True)
        self.failure_screenshot_dir = path

    def _capture_failure_screenshot(self, action) -> Optional[str]:
        """Best-effort screenshot save when an action raises. Returns path or None."""
        if not self.failure_screenshot_dir:
            return None
        png = _try_selenium_screenshot() or _try_playwright_screenshot()
        if not png:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_name = str(action[0] if isinstance(action, list) and action else "unknown")
        target = Path(self.failure_screenshot_dir) / f"{timestamp}_{safe_name}.png"
        try:
            target.write_bytes(png)
            return str(target)
        except OSError as error:
            web_runner_logger.error(f"failure screenshot write failed: {error!r}")
            return None

    def set_allow_arbitrary_script(self, enabled: bool) -> None:
        """
        切換是否允許 ``WR_execute_script`` / ``WR_pw_evaluate`` / CDP 命令
        Toggle the gate for arbitrary-script commands. Disable when action
        JSON files are not fully trusted.
        """
        self.allow_arbitrary_script = bool(enabled)

    def _execute_event(self, action: list):
        """
        執行事件字典中的函式
        Execute a function from event_dict

        :param action: 指令清單，例如 ["函式名稱", {參數}] 或 ["函式名稱"]
                       Action list, e.g., ["function_name", {params}] or ["function_name"]
        :return: 執行結果 / return value of the executed function
        """
        if action[0] in _ARBITRARY_SCRIPT_COMMANDS and not self.allow_arbitrary_script:
            raise WebRunnerExecuteException(
                f"arbitrary-script command {action[0]!r} is disabled; "
                "call WR_set_allow_arbitrary_script(true) to enable"
            )
        event = self.event_dict.get(action[0])
        if event is None:
            raise WebRunnerExecuteException(executor_data_error + " unknown command: " + str(action[0]))
        if len(action) == 2:
            if isinstance(action[1], dict):
                # 使用關鍵字參數呼叫
                # Call with keyword arguments
                return event(**action[1])
            else:
                # 使用位置參數呼叫
                # Call with positional arguments
                return event(*action[1])
        elif len(action) == 1:
            # 無參數呼叫
            # Call without arguments
            return event()
        else:
            # 格式錯誤，拋出例外
            # Invalid format, raise exception
            raise WebRunnerExecuteException(executor_data_error + " " + str(action))

    def execute_action(self, action_list: Union[list, dict]) -> dict:
        """
        執行一系列動作
        Execute a list of actions

        :param action_list: 動作清單，例如：
           Action list, e.g.:
           [
               ["WR_get_webdriver_manager", {"webdriver_name": "firefox"}],
               ["WR_to_url", {"url": "https://www.google.com"}],
               ["WR_quit"]
           ]
        :return: 執行紀錄字典 {動作描述: 回傳值}
                 Execution record dict {action: response}
        """
        web_runner_logger.info(f"execute_action, action_list: {action_list}")

        # 如果傳入的是 dict，則嘗試取出 "webdriver_wrapper" 的動作清單
        # If input is dict, extract "webdriver_wrapper" action list
        if type(action_list) is dict:
            action_list = action_list.get("webdriver_wrapper", None)
            if action_list is None:
                web_runner_logger.error(
                    f"execute_action, action_list: {action_list}, "
                    f"failed: {WebRunnerExecuteException(executor_list_error)}")
                raise WebRunnerExecuteException(executor_list_error)

        execute_record_dict = {}

        # 檢查 action_list 是否為合法的 list
        # Validate action_list
        try:
            if len(action_list) == 0 or isinstance(action_list, list) is False:
                web_runner_logger.error(
                    f"execute_action, action_list: {action_list}, "
                    f"failed: {WebRunnerExecuteException(executor_list_error)}")
                raise WebRunnerExecuteException(executor_list_error)
        except Exception as error:
            web_runner_logger.error(
                f"execute_action, action_list: {action_list}, "
                f"failed: {repr(error)}")

        # 逐一執行動作
        # Execute each action in the list
        for action in action_list:
            try:
                event_response = self._execute_with_retry(action)
                execute_record = "execute: " + str(action)
                execute_record_dict.update({execute_record: event_response})
            except Exception as error:
                web_runner_logger.error(
                    f"execute_action, action_list: {action_list}, "
                    f"action: {action}, failed: {repr(error)}")
                execute_record = "execute: " + str(action)
                screenshot_path = self._capture_failure_screenshot(action)
                if screenshot_path:
                    execute_record_dict.update({
                        execute_record: f"{repr(error)} (failure screenshot: {screenshot_path})"
                    })
                else:
                    execute_record_dict.update({execute_record: repr(error)})

        # 輸出執行結果
        # Print execution results
        for key, value in execute_record_dict.items():
            print(key)
            print(value)

        return execute_record_dict

    def execute_files(self, execute_files_list: list) -> list:
        """
        從檔案載入並執行動作
        Execute actions from files

        :param execute_files_list: 檔案路徑清單 / list of file paths
        :return: 每個檔案的執行結果清單 / list of execution results
        """
        web_runner_logger.info(f"execute_files, execute_files_list: {execute_files_list}")
        execute_detail_list = []
        for file in execute_files_list:
            # 讀取 JSON 檔案並執行
            # Read JSON file and execute
            execute_detail_list.append(self.execute_action(read_action_json(file)))
        return execute_detail_list


# 建立全域 Executor 實例
# Create global Executor instance
executor = Executor()
package_manager.executor = executor

def add_command_to_executor(command_dict: dict):
    """
    動態新增指令到 Executor
    Dynamically add commands to Executor

    :param command_dict: {指令名稱: 函式} / {command_name: function}
    """
    for command_name, command in command_dict.items():
        if isinstance(command, (types.MethodType, types.FunctionType)):
            executor.event_dict.update({command_name: command})
        else:
            raise WebRunnerAddCommandException(add_command_exception_tag)

def execute_action(action_list: list) -> dict:
    """
    全域方法：執行動作清單
    Global method: execute action list
    """
    return executor.execute_action(action_list)

def execute_files(execute_files_list: list) -> list:
    """
    全域方法：執行檔案中的動作
    Global method: execute actions from files
    """
    return executor.execute_files(execute_files_list)