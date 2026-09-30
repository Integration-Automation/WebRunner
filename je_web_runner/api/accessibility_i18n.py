"""Facade: Accessibility, localisation and visual checks: screen readers, colours, RTL, OCR."""
from je_web_runner.utils.dst_boundary_test.boundary import (
    DstBoundaryError, Transition, DstBoundary, find_boundaries, is_nonexistent_local_time, is_ambiguous_local_time,
    ScheduledFire, expected_fires_around_boundary, assert_no_duplicate_fires, assert_fired_around,
)
from je_web_runner.utils.forced_colors_mode.modes import (
    ForcedColorsModeError, ColorScheme, ReducedMotion, ForcedColors, Contrast, MediaProfile, apply_profile,
    StyleSnapshot, ElementDiff, diff_snapshot, ModeAuditReport, audit_modes, assert_no_invisible,
)
from je_web_runner.utils.number_currency_locale.locale import (
    NumberCurrencyLocaleError, NumberRules, CurrencyRules, assert_number_format, assert_currency_symbol,
    assert_date_format,
)
from je_web_runner.utils.ocr_assert.ocr import (
    OcrAssertError, normalise_text, fuzzy_ratio, tesseract_backend, extract_text, OcrMatchResult,
    assert_text_contains, assert_text_fuzzy, assert_text_any,
)
from je_web_runner.utils.pseudo_localization.pseudo import (
    PseudoLocalizationError, PseudoConfig, pseudo_localize, pseudo_localize_dict, HardcodedHit, PseudoAuditReport,
    scan_for_hardcoded,
)
from je_web_runner.utils.rtl_layout_verify.verify import (
    RtlLayoutVerifyError, ElementBox, Snapshot, parse_snapshot, assert_document_rtl, assert_logical_properties,
    assert_visual_order_reversed, assert_bidi_isolation,
)
from je_web_runner.utils.screen_reader_runner.reader import (
    ScreenReaderError, ViolationKind, Utterance, Violation as ScreenReaderRunnerViolation, ScreenReaderTranscript,
    walk_tree, assert_no_violations as screen_reader_runner_assert_no_violations, assert_reads,
)
from je_web_runner.utils.visual_ai.perceptual import (
    VisualAIError, HashResult, average_hash, difference_hash, perceptual_hash, hamming_distance, hash_similarity,
    SimilarityResult, compare_images, assert_visual_similar,
)
from je_web_runner.utils.visual_regression.visual_diff import (
    VisualRegressionError, capture_baseline, compare_with_baseline, playwright_capture_baseline,
    playwright_compare_with_baseline,
)
from je_web_runner.utils.wcag22_touch_target.touch import (
    Wcag22TouchTargetError, TargetException, Target, Violation as Wcag22TouchTargetViolation, parse_targets, audit,
    assert_no_violations as wcag22_touch_target_assert_no_violations,
)

__all__ = [
    "DstBoundaryError", "Transition", "DstBoundary", "find_boundaries", "is_nonexistent_local_time",
    "is_ambiguous_local_time", "ScheduledFire", "expected_fires_around_boundary", "assert_no_duplicate_fires",
    "assert_fired_around", "ForcedColorsModeError", "ColorScheme", "ReducedMotion", "ForcedColors", "Contrast",
    "MediaProfile", "apply_profile", "StyleSnapshot", "ElementDiff", "diff_snapshot", "ModeAuditReport",
    "audit_modes", "assert_no_invisible", "NumberCurrencyLocaleError", "NumberRules", "CurrencyRules",
    "assert_number_format", "assert_currency_symbol", "assert_date_format", "OcrAssertError", "normalise_text",
    "fuzzy_ratio", "tesseract_backend", "extract_text", "OcrMatchResult", "assert_text_contains",
    "assert_text_fuzzy", "assert_text_any", "PseudoLocalizationError", "PseudoConfig", "pseudo_localize",
    "pseudo_localize_dict", "HardcodedHit", "PseudoAuditReport", "scan_for_hardcoded", "RtlLayoutVerifyError",
    "ElementBox", "Snapshot", "parse_snapshot", "assert_document_rtl", "assert_logical_properties",
    "assert_visual_order_reversed", "assert_bidi_isolation", "ScreenReaderError", "ViolationKind", "Utterance",
    "ScreenReaderRunnerViolation", "ScreenReaderTranscript", "walk_tree",
    "screen_reader_runner_assert_no_violations", "assert_reads", "VisualAIError", "HashResult", "average_hash",
    "difference_hash", "perceptual_hash", "hamming_distance", "hash_similarity", "SimilarityResult",
    "compare_images", "assert_visual_similar", "VisualRegressionError", "capture_baseline",
    "compare_with_baseline", "playwright_capture_baseline", "playwright_compare_with_baseline",
    "Wcag22TouchTargetError", "TargetException", "Target", "Wcag22TouchTargetViolation", "parse_targets", "audit",
    "wcag22_touch_target_assert_no_violations",
]
