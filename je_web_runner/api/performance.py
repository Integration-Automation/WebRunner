"""Facade: Performance: Core Web Vitals, Lighthouse, bundle and third-party budgets, load, emulation."""
from je_web_runner.utils.bundle_budget.budget import (
    BundleBudgetError, AssetKind, Asset, assets_from_har, Budget, BudgetBreach, BudgetReport, evaluate_budget,
    assert_within_budget as bundle_budget_assert_within_budget, report_markdown as bundle_budget_report_markdown,
)
from je_web_runner.utils.bundle_diff_pr.diff import (
    BundleDiffPrError, AssetDelta, BundleDiff, diff_hars, assert_under_max_growth,
    report_markdown as bundle_diff_pr_report_markdown,
)
from je_web_runner.utils.critical_css_audit.audit import (
    CriticalCssAuditError, CssReport, analyse, assert_has_inline_critical, assert_inline_within_budget,
    assert_external_preloaded,
)
from je_web_runner.utils.font_loading_strategy.strategy import (
    FontLoadingStrategyError, Display, FontFace, parse_font_faces, assert_no_missing_display,
    assert_display_strategy, assert_size_adjust_for_fallback,
)
from je_web_runner.utils.hydration_check.check import (
    HydrationCheckError, HydrationFinding, scan_console, diff_dom, HydrationReport, audit, assert_no_mismatch,
)
from je_web_runner.utils.hydration_streaming.timing import (
    HydrationStreamingError, BoundaryTiming, StreamingReport, parse_log as hydration_streaming_parse_log,
    assert_all_arrived, assert_arrival_under, assert_interactive_under, assert_order,
)
from je_web_runner.utils.inp_tracker.tracker import (
    InpTrackerError, InpRating, build_install_script as inp_tracker_build_install_script, InteractionEvent,
    parse_log as inp_tracker_parse_log, InpReport, assert_inp_under, assert_no_poor_interactions,
)
from je_web_runner.utils.lcp_image_audit.audit import (
    LcpImageAuditError, LcpCandidate, parse_candidate, assert_lcp_preloaded, assert_lcp_not_lazy_loaded,
    assert_fetchpriority_high,
)
from je_web_runner.utils.lighthouse.lighthouse_runner import (
    LighthouseError, run_lighthouse, assert_scores,
)
from je_web_runner.utils.lighthouse_regression.regression import (
    LighthouseRegressionError, LighthouseSnapshot, parse_report, ScoreDelta, RegressionReport, diff,
    assert_no_score_regression, assert_metric_within,
)
from je_web_runner.utils.load_test.locust_wrapper import (
    LoadTestError, build_http_user_class, run_locust,
)
from je_web_runner.utils.long_animation_frame.frames import (
    LongAnimationFrameError, build_install_script as long_animation_frame_build_install_script, ScriptAttribution,
    LongFrame, parse_log as long_animation_frame_parse_log, LoafReport, assert_no_frame_over,
    assert_total_blocking_under,
)
from je_web_runner.utils.memory_pressure_emulate.emulate import (
    MemoryPressureError, PressureLevel, EmulationProfile, cdp_payloads, PressureRunOutcome, run_under_profile,
    assert_passed_under_pressure,
)
from je_web_runner.utils.network_emulation.throttling import (
    NetworkEmulationError, list_presets, selenium_emulate_network, selenium_clear_throttling,
    playwright_emulate_network, playwright_clear_throttling,
)
from je_web_runner.utils.resource_hints_audit.hints import (
    ResourceHintsAuditError, HintKind, Hint, parse_hints, assert_preload_has_as, find_unused_hints,
    assert_no_unused_hints, assert_origin_preconnected,
)
from je_web_runner.utils.third_party_block_test.block import (
    ThirdPartyBlockError, Resilience, Vendor, builtin_vendors, BlockOutcome, BlockReport, run_block_matrix,
    assert_resilient_to,
)
from je_web_runner.utils.third_party_budget.budget import (
    ThirdPartyBudgetError, ThirdPartyRequest, classify_har, ThirdPartyBudget, ThirdPartyReport,
    evaluate as third_party_budget_evaluate, assert_within_budget as third_party_budget_assert_within_budget,
)
from je_web_runner.utils.web_vitals.vitals import (
    WebVitalsError, rate, measure_page, lighthouse_measurement, evaluate as web_vitals_evaluate, write_reports,
    assert_web_vitals,
)

__all__ = [
    "BundleBudgetError", "AssetKind", "Asset", "assets_from_har", "Budget", "BudgetBreach", "BudgetReport",
    "evaluate_budget", "bundle_budget_assert_within_budget", "bundle_budget_report_markdown", "BundleDiffPrError",
    "AssetDelta", "BundleDiff", "diff_hars", "assert_under_max_growth", "bundle_diff_pr_report_markdown",
    "CriticalCssAuditError", "CssReport", "analyse", "assert_has_inline_critical", "assert_inline_within_budget",
    "assert_external_preloaded", "FontLoadingStrategyError", "Display", "FontFace", "parse_font_faces",
    "assert_no_missing_display", "assert_display_strategy", "assert_size_adjust_for_fallback",
    "HydrationCheckError", "HydrationFinding", "scan_console", "diff_dom", "HydrationReport", "audit",
    "assert_no_mismatch", "HydrationStreamingError", "BoundaryTiming", "StreamingReport",
    "hydration_streaming_parse_log", "assert_all_arrived", "assert_arrival_under", "assert_interactive_under",
    "assert_order", "InpTrackerError", "InpRating", "inp_tracker_build_install_script", "InteractionEvent",
    "inp_tracker_parse_log", "InpReport", "assert_inp_under", "assert_no_poor_interactions", "LcpImageAuditError",
    "LcpCandidate", "parse_candidate", "assert_lcp_preloaded", "assert_lcp_not_lazy_loaded",
    "assert_fetchpriority_high", "LighthouseError", "run_lighthouse", "assert_scores", "LighthouseRegressionError",
    "LighthouseSnapshot", "parse_report", "ScoreDelta", "RegressionReport", "diff", "assert_no_score_regression",
    "assert_metric_within", "LoadTestError", "build_http_user_class", "run_locust", "LongAnimationFrameError",
    "long_animation_frame_build_install_script", "ScriptAttribution", "LongFrame",
    "long_animation_frame_parse_log", "LoafReport", "assert_no_frame_over", "assert_total_blocking_under",
    "MemoryPressureError", "PressureLevel", "EmulationProfile", "cdp_payloads", "PressureRunOutcome",
    "run_under_profile", "assert_passed_under_pressure", "NetworkEmulationError", "list_presets",
    "selenium_emulate_network", "selenium_clear_throttling", "playwright_emulate_network",
    "playwright_clear_throttling", "ResourceHintsAuditError", "HintKind", "Hint", "parse_hints",
    "assert_preload_has_as", "find_unused_hints", "assert_no_unused_hints", "assert_origin_preconnected",
    "ThirdPartyBlockError", "Resilience", "Vendor", "builtin_vendors", "BlockOutcome", "BlockReport",
    "run_block_matrix", "assert_resilient_to", "ThirdPartyBudgetError", "ThirdPartyRequest", "classify_har",
    "ThirdPartyBudget", "ThirdPartyReport", "third_party_budget_evaluate",
    "third_party_budget_assert_within_budget", "WebVitalsError", "rate", "measure_page", "lighthouse_measurement",
    "web_vitals_evaluate", "write_reports", "assert_web_vitals",
]
