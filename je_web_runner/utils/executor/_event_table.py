"""
WR_* 指令表：把 action JSON 的指令名稱對應到實際函式
The WR_* command table: maps each action-JSON command name to its callable.

The table keeps the historical registration order. Entries that must call the
owning :class:`~je_web_runner.utils.executor.action_executor.Executor` are
wrapped in :class:`_Bound` and resolved by :func:`build_event_dict`.
"""
from __future__ import annotations

import inspect
import time
from typing import Any, Callable

from je_web_runner.manager.webrunner_manager import web_runner
from je_web_runner.utils.generate_report.generate_html_report import generate_html
from je_web_runner.utils.generate_report.generate_html_report import generate_html_report
from je_web_runner.utils.generate_report.interactive_html_report import generate_interactive_html_report
from je_web_runner.utils.generate_report.generate_json_report import generate_json
from je_web_runner.utils.generate_report.generate_json_report import generate_json_report
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml
from je_web_runner.utils.generate_report.generate_xml_report import generate_xml_report
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml
from je_web_runner.utils.generate_report.generate_junit_xml_report import generate_junit_xml_report
from je_web_runner.utils.generate_report.generate_allure_report import generate_allure
from je_web_runner.utils.generate_report.generate_allure_report import generate_allure_report
from je_web_runner.utils.generate_report.report_manifest import (
    expected_paths as _report_expected_paths,
    generate_all_reports as _report_generate_all,
)
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
from je_web_runner.utils.web_vitals import vitals as _web_vitals
from je_web_runner.utils.load_test import locust_wrapper as _locust
from je_web_runner.utils.test_management import jira_client as _jira
from je_web_runner.utils.test_management import testrail_client as _testrail
from je_web_runner.utils.run_ledger import flaky as _flaky
from je_web_runner.utils.run_ledger import ledger as _ledger
from je_web_runner.utils.run_ledger import classifier as _classifier
from je_web_runner.utils.service_worker import sw_control as _sw
from je_web_runner.utils.storage import browser_storage as _storage
from je_web_runner.utils.cdp.cdp_commands import (
    playwright_cdp as _cdp_playwright,
    reset_playwright_cdp_sessions as _cdp_reset,
    selenium_cdp as _cdp_selenium,
)
from je_web_runner.utils.network_emulation import throttling as _throttle
from je_web_runner.utils.test_data import faker_integration as _fakerint
from je_web_runner.utils.extensions import extension_loader as _ext
from je_web_runner.utils.dom_traversal import shadow_iframe as _dom
from je_web_runner.utils.file_transfer import file_helpers as _ft
from je_web_runner.utils.linter import action_linter as _linter
from je_web_runner.utils.linter import migration as _migration
from je_web_runner.utils.schema import action_schema as _schema
from je_web_runner.utils.docs import command_reference as _docs
from je_web_runner.utils.database import db_validate as _db
from je_web_runner.utils.scheduler import cron_runner as _scheduler
from je_web_runner.utils.multi_user import matrix as _matrix
from je_web_runner.utils.replay_studio import replay_studio as _replay
from je_web_runner.utils.auth import oauth as _oauth
from je_web_runner.utils.factories import factory as _factories
from je_web_runner.utils.testcontainers_integration import containers as _tc
from je_web_runner.utils.dashboard import live_dashboard as _dashboard
from je_web_runner.utils.sharding import shard as _sharding
from je_web_runner.utils.appium_integration import appium_driver as _appium
from je_web_runner.utils.ai_assist import llm_assist as _llm
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
from je_web_runner.utils.bidi.selenium_events import selenium_bidi_events as _bidi_events
from je_web_runner.utils import autocontrol_bridge as _autocontrol
from je_web_runner.utils.async_executor.commands import ASYNC_COMMANDS as _ASYNC_COMMANDS
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor._playwright_commands import PLAYWRIGHT_COMMANDS
from je_web_runner.utils.json.json_validator import validate_action_file, validate_action_json
from je_web_runner.utils.package_manager.package_manager_class import package_manager
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.visual_regression.visual_diff import capture_baseline as _visual_capture_baseline
from je_web_runner.utils.visual_regression.visual_diff import compare_with_baseline as _visual_compare
from je_web_runner.utils.recorder.browser_recorder import pull_events as _recorder_pull_events
from je_web_runner.utils.recorder.browser_recorder import save_recording as _recorder_save_recording
from je_web_runner.utils.recorder.browser_recorder import start_recording as _recorder_start
from je_web_runner.utils.recorder.browser_recorder import stop_recording as _recorder_stop
from je_web_runner.utils.test_record.test_record_class import test_record_instance
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance


def _sleep_seconds(seconds: int | float = 1) -> float:
    """
    阻塞當前執行緒指定秒數，回傳實際睡眠的秒數。
    Block the calling thread for ``seconds`` (positive number). Negative
    or non-numeric values raise :class:`ValueError` so a typo can't
    silently no-op an action JSON pipeline.
    """
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise ValueError(f"WR_sleep seconds must be a number, got {type(seconds).__name__}")
    if seconds < 0:
        raise ValueError(f"WR_sleep seconds must be >= 0, got {seconds}")
    time.sleep(float(seconds))
    return float(seconds)


def _async_only(name: str, command: Callable[..., Any]) -> Callable[..., Any]:
    """A sync-table stand-in for an async-only ``WR_apw_*`` command: same signature and doc, refuses to run."""
    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise WebRunnerExecuteException(
            f"{name} runs only in the async executor: python -m je_web_runner -d DIR --parallel-mode async, "
            "or je_web_runner.utils.async_executor.AsyncExecutor")
    parameters = list(inspect.signature(command).parameters.values())[1:]  # the executor passes the session
    refuse.__signature__ = inspect.signature(command).replace(parameters=parameters)
    refuse.__doc__ = f"{(command.__doc__ or '').strip()}\n\nAsync executor only (``--parallel-mode async``)."
    refuse.__name__ = command.__name__
    return refuse


class _Bound:
    """A table entry that needs the owning executor, e.g. ``WR_execute_action``."""

    def __init__(self, factory: Callable[[Any], Callable[..., Any]]) -> None:
        self.factory = factory


# 事件字典：將字串名稱對應到實際可執行的函式
# Event dictionary: map string keys to actual callable functions
COMMANDS: dict[str, Any] = {
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
        "WR_sleep": _sleep_seconds,
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
        "WR_save_screenshot": webdriver_wrapper_instance.save_screenshot,
        "WR_save_full_page_screenshot": webdriver_wrapper_instance.save_full_page_screenshot,
        "WR_print_page": webdriver_wrapper_instance.print_page,
        "WR_get_log": webdriver_wrapper_instance.get_log,
        "WR_single_quit": webdriver_wrapper_instance.quit,

        # webdriver wrapper — advanced (mixin additions)
        "WR_attach_to_existing_browser": webdriver_wrapper_instance.attach_to_existing_browser,
        "WR_execute_cdp_cmd": webdriver_wrapper_instance.execute_cdp_cmd,
        "WR_reload": webdriver_wrapper_instance.reload,
        "WR_bring_to_front": webdriver_wrapper_instance.bring_to_front,
        "WR_scroll_to_top": webdriver_wrapper_instance.scroll_to_top,
        "WR_scroll_to_bottom": webdriver_wrapper_instance.scroll_to_bottom,
        "WR_switch_to_window_by_url": webdriver_wrapper_instance.switch_to_window_by_url,
        "WR_switch_to_window_by_title": webdriver_wrapper_instance.switch_to_window_by_title,
        "WR_get_current_url": webdriver_wrapper_instance.get_current_url,
        "WR_get_title": webdriver_wrapper_instance.get_title,
        "WR_get_page_source": webdriver_wrapper_instance.get_page_source,
        "WR_get_window_handles": webdriver_wrapper_instance.get_window_handles,
        "WR_get_current_window_handle": webdriver_wrapper_instance.get_current_window_handle,
        "WR_new_window": webdriver_wrapper_instance.new_window,
        "WR_close_window": webdriver_wrapper_instance.close_window,
        "WR_save_cookies": webdriver_wrapper_instance.save_cookies,
        "WR_load_cookies": webdriver_wrapper_instance.load_cookies,
        "WR_clear_origin_storage": webdriver_wrapper_instance.clear_origin_storage,
        "WR_add_script_to_evaluate_on_new_document":
            webdriver_wrapper_instance.add_script_to_evaluate_on_new_document,
        "WR_set_user_agent": webdriver_wrapper_instance.set_user_agent,
        "WR_set_extra_http_headers": webdriver_wrapper_instance.set_extra_http_headers,
        "WR_set_geolocation": webdriver_wrapper_instance.set_geolocation,
        "WR_set_timezone": webdriver_wrapper_instance.set_timezone,
        "WR_set_locale": webdriver_wrapper_instance.set_locale,
        "WR_set_device_metrics": webdriver_wrapper_instance.set_device_metrics,
        "WR_clear_device_metrics": webdriver_wrapper_instance.clear_device_metrics,
        "WR_clear_geolocation_override": webdriver_wrapper_instance.clear_geolocation_override,
        "WR_set_network_conditions": webdriver_wrapper_instance.set_network_conditions,
        "WR_block_urls": webdriver_wrapper_instance.block_urls,
        "WR_unblock_urls": webdriver_wrapper_instance.unblock_urls,
        "WR_set_cache_disabled": webdriver_wrapper_instance.set_cache_disabled,
        "WR_set_download_directory": webdriver_wrapper_instance.set_download_directory,
        "WR_enable_fetch_interception": webdriver_wrapper_instance.enable_fetch_interception,
        "WR_disable_fetch_interception": webdriver_wrapper_instance.disable_fetch_interception,
        "WR_fetch_continue_request": webdriver_wrapper_instance.continue_request,
        "WR_fetch_fulfill_request": webdriver_wrapper_instance.fulfill_request,
        "WR_fetch_fail_request": webdriver_wrapper_instance.fail_request,

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
        "WR_generate_interactive_html_report": generate_interactive_html_report,
        "WR_generate_json": generate_json,
        "WR_generate_json_report": generate_json_report,
        "WR_generate_xml": generate_xml,
        "WR_generate_xml_report": generate_xml_report,
        "WR_generate_junit_xml": generate_junit_xml,
        "WR_generate_junit_xml_report": generate_junit_xml_report,
        "WR_generate_allure": generate_allure,
        "WR_generate_allure_report": generate_allure_report,
        "WR_generate_all_reports": _report_generate_all,
        "WR_report_expected_paths": _report_expected_paths,

        # execute
        "WR_execute_action": _Bound(lambda executor: executor.execute_action),
        "WR_execute_files": _Bound(lambda executor: executor.execute_files),

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
        "WR_run_with_dataset": _Bound(lambda executor: lambda action_data, rows: run_with_dataset(
            action_data, rows, executor.execute_action
        )),

        # failure auto-screenshot
        "WR_set_failure_screenshot_dir": _Bound(lambda executor: executor.set_failure_screenshot_dir),

        # retry policy
        "WR_set_retry_policy": _Bound(lambda executor: executor.set_retry_policy),

        # security: arbitrary-script gate
        "WR_set_allow_arbitrary_script": _Bound(lambda executor: executor.set_allow_arbitrary_script),
        "WR_set_raise_wrapper_errors": _Bound(lambda executor: executor.set_raise_wrapper_errors),

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

        # network throttling presets
        "WR_throttle": _throttle.selenium_emulate_network,
        "WR_throttle_clear": _throttle.selenium_clear_throttling,
        "WR_pw_throttle": _throttle.playwright_emulate_network,
        "WR_pw_throttle_clear": _throttle.playwright_clear_throttling,
        "WR_throttle_presets": _throttle.list_presets,

        # faker (random test data)
        "WR_faker_seed": _fakerint.seed_faker,
        "WR_faker": _fakerint.fake_value,
        "WR_faker_email": _fakerint.fake_email,
        "WR_faker_name": _fakerint.fake_name,
        "WR_faker_first_name": _fakerint.fake_first_name,
        "WR_faker_last_name": _fakerint.fake_last_name,
        "WR_faker_phone": _fakerint.fake_phone,
        "WR_faker_address": _fakerint.fake_address,
        "WR_faker_uuid": _fakerint.fake_uuid,
        "WR_faker_credit_card": _fakerint.fake_credit_card,
        "WR_faker_url": _fakerint.fake_url,
        "WR_faker_user_agent": _fakerint.fake_user_agent,
        "WR_faker_password": _fakerint.fake_password,
        "WR_faker_text": _fakerint.fake_text,

        # browser extension loaders
        "WR_chrome_options_with_extension": _ext.selenium_chrome_options_with_extension,
        "WR_pw_extension_args": _ext.playwright_extension_launch_args,

        # shadow DOM / iframe traversal
        "WR_shadow_query": _dom.selenium_query_in_shadow,
        "WR_pw_shadow_query": _dom.playwright_query_in_shadow,
        "WR_pw_shadow_selector": _dom.playwright_shadow_selector,
        "WR_iframe_switch_chain": _dom.selenium_switch_iframe_chain,
        "WR_iframe_back_to_default": _dom.selenium_back_to_default,
        "WR_pw_frame_locator_chain": _dom.playwright_frame_locator_chain,

        # file upload / download
        "WR_upload_file": _ft.selenium_upload_file,
        "WR_pw_upload_file": _ft.playwright_upload_file,
        "WR_wait_for_download": _ft.wait_for_download,
        "WR_list_new_downloads": _ft.list_new_downloads,
        "WR_snapshot_directory": _ft.snapshot_directory,

        # action linter
        "WR_lint_action": _linter.lint_action,
        "WR_lint_action_file": _linter.lint_action_file,
        "WR_lint_severity_counts": _linter.severity_counts,

        # migration helper
        "WR_migrate_action": _migration.migrate_action,
        "WR_migrate_action_file": _migration.migrate_action_file,
        "WR_migrate_directory": _migration.migrate_directory,

        # JSON Schema export
        "WR_build_action_schema": _schema.build_action_schema,
        "WR_export_action_schema": _schema.export_schema,

        # auto-generated docs
        "WR_build_command_reference": _docs.build_command_reference,
        "WR_export_command_reference": _docs.export_command_reference,
        "WR_list_commands": _docs.list_commands,

        # OpenTelemetry tracing
        "WR_set_action_span_factory": _Bound(lambda executor: executor.set_action_span_factory),

        # database validation
        "WR_db_query": _db.db_query,
        "WR_db_assert_count": _db.db_assert_count,
        "WR_db_assert_value": _db.db_assert_value,
        "WR_db_assert_exists": _db.db_assert_exists,
        "WR_db_assert_empty": _db.db_assert_empty,

        # scheduler
        "WR_schedule": _scheduler.schedule,
        "WR_run_scheduler_for": _scheduler.run_scheduler_for,
        "WR_run_scheduler_forever": _scheduler.run_scheduler_forever,
        "WR_stop_scheduler": _scheduler.stop_scheduler,
        "WR_scheduler_counts": _scheduler.scheduler_counts,
        "WR_reset_scheduler": _scheduler.reset_scheduler,

        # multi-user matrix runner
        "WR_run_for_users": _matrix.run_for_users,

        # failure classifier
        "WR_classify_error": _classifier.classify_error,
        "WR_classify_failure": _classifier.classify,
        "WR_classify_failures": _classifier.classify_failures,

        # replay studio (HTML timeline)
        "WR_build_replay_html": _replay.build_replay_html,
        "WR_export_replay_studio": _replay.export_replay_studio,

        # OAuth2 / OIDC
        "WR_oauth_client_credentials": _oauth.client_credentials_token,
        "WR_oauth_password_grant": _oauth.password_grant_token,
        "WR_oauth_refresh_token": _oauth.refresh_token_grant,
        "WR_oauth_get_cached": _oauth.get_cached_token,
        "WR_oauth_clear_cache": _oauth.clear_token_cache,
        "WR_oauth_bearer_header": _oauth.bearer_header,

        # factory pattern helpers
        "WR_user_factory": _factories.user_factory,
        "WR_order_factory": _factories.order_factory,
        "WR_product_factory": _factories.product_factory,

        # testcontainers
        "WR_tc_postgres": _tc.start_postgres,
        "WR_tc_redis": _tc.start_redis,
        "WR_tc_generic": _tc.start_generic,
        "WR_tc_stop": _tc.stop_container,
        "WR_tc_cleanup_all": _tc.cleanup_all,
        "WR_tc_started_count": _tc.started_count,

        # live dashboard
        "WR_dashboard_start": _dashboard.start_dashboard,
        "WR_dashboard_stop": _dashboard.stop_dashboard,

        # sharding
        "WR_parse_shard_spec": _sharding.parse_shard_spec,
        "WR_partition": _sharding.partition,
        "WR_partition_with_spec": _sharding.partition_with_spec,

        # Appium
        "WR_appium_start": _appium.start_appium_session,
        "WR_appium_quit": _appium.quit_appium_session,
        "WR_appium_android_caps": _appium.build_android_caps,
        "WR_appium_ios_caps": _appium.build_ios_caps,

        # LLM scaffolds
        "WR_llm_set_callable": _llm.set_llm_callable,
        "WR_llm_has_callable": _llm.has_llm_callable,
        "WR_llm_suggest_locator": _llm.suggest_locator,
        "WR_llm_generate_actions": _llm.generate_actions_from_prompt,
        "WR_llm_self_heal_locator": _llm.llm_self_heal_locator,

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
        "WR_assert_web_vitals": _web_vitals.assert_web_vitals,

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

        **PLAYWRIGHT_COMMANDS,

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

        # ----- twins of Playwright commands (these raise on failure) -----
        "WR_wait_for_element": webdriver_wrapper_instance.wait_for_element,
        "WR_wait_for_url": webdriver_wrapper_instance.wait_for_url,
        "WR_wait_for_title": webdriver_wrapper_instance.wait_for_title,
        "WR_wait_for_ready_state": webdriver_wrapper_instance.wait_for_ready_state,
        "WR_find_element_by": webdriver_wrapper_instance.find_element_by,
        "WR_find_elements_by": webdriver_wrapper_instance.find_elements_by,
        "WR_alert_accept": webdriver_wrapper_instance.alert_accept,
        "WR_alert_dismiss": webdriver_wrapper_instance.alert_dismiss,
        "WR_alert_text": webdriver_wrapper_instance.alert_text,
        "WR_emulate_device": webdriver_wrapper_instance.emulate_device,
        "WR_list_devices": webdriver_wrapper_instance.list_devices,
        "WR_grant_permissions": webdriver_wrapper_instance.grant_permissions,
        "WR_clear_permissions": webdriver_wrapper_instance.clear_permissions,
        "WR_clock_freeze": webdriver_wrapper_instance.clock_freeze,
        "WR_element_check": web_runner.webdriver_element.check,
        "WR_element_uncheck": web_runner.webdriver_element.uncheck,
        "WR_element_hover": web_runner.webdriver_element.hover,
        "WR_element_inner_text": web_runner.webdriver_element.inner_text,
        "WR_element_inner_html": web_runner.webdriver_element.inner_html,

        # ----- W3C BiDi (driver started with enable_bidi=True): capture, HAR, mocks -----
        "WR_event_capture_start": _bidi_events.start_event_capture,
        "WR_event_capture_stop": _bidi_events.stop_event_capture,
        "WR_event_capture_clear": _bidi_events.clear_event_capture,
        "WR_console_messages": _bidi_events.console_messages,
        "WR_network_responses": _bidi_events.network_responses,
        "WR_dom_mutations": _bidi_events.dom_mutation_records,
        "WR_assert_no_console_errors": _bidi_events.capture.assert_no_console_errors,
        "WR_assert_no_5xx": _bidi_events.capture.assert_no_5xx,
        "WR_assert_no_4xx_or_5xx": _bidi_events.capture.assert_no_4xx_or_5xx,
        "WR_start_har_recording": _bidi_events.start_har_recording,
        "WR_stop_har_recording": _bidi_events.stop_har_recording,
        "WR_route_mock": _bidi_events.route_mock,
        "WR_route_mock_json": _bidi_events.route_mock_json,
        "WR_route_unmock": _bidi_events.route_unmock,
        "WR_route_clear": _bidi_events.route_clear,

        # ----- AutoControl bridge (optional je_auto_control, imported only when a command runs) -----
        "WR_ac_available": _autocontrol.ac_available,
        "WR_ac_list_commands": _autocontrol.ac_list_commands,
        "WR_ac_run": _autocontrol.ac_run,
        "WR_ac_run_actions": _autocontrol.ac_run_actions,
        "WR_ac_fill_native_file_dialog": _autocontrol.fill_native_file_dialog,
        "WR_ac_assert_image_on_screen": _autocontrol.assert_image_on_screen,
        "WR_ac_click_element_native": _autocontrol.click_element_native,

        # ----- async executor only (WR_apw_*): listed here so references, schema and validation know them -----
        **{name: _async_only(name, command) for name, command in _ASYNC_COMMANDS.items()},
}


def build_event_dict(executor: Any) -> dict[str, Callable[..., Any]]:
    """Return a fresh command table for ``executor`` (each call builds a new dict)."""
    return {
        name: value.factory(executor) if isinstance(value, _Bound) else value
        for name, value in COMMANDS.items()
    }
