"""Facade: Language-model helpers: assist, repair, generation, triage, and checks of LLM features."""
from je_web_runner.utils.ai_assist.llm_assist import (
    LLMAssistError, set_llm_callable, has_llm_callable, suggest_locator, generate_actions_from_prompt,
    llm_self_heal_locator, explain_failure,
)
from je_web_runner.utils.test_auto_repair.repair import (
    TestAutoRepairError, collect_git_diff, RepairPlan, propose_repair, repair_from_bundle, apply_repair,
    render_repair_markdown,
)
from je_web_runner.utils.edge_case_generator.generator import (
    EdgeCaseGeneratorError, EdgeCaseCategory, EdgeCase, EdgeCaseSuite, generate_edge_cases,
    generate_edge_cases_from_file, write_suite_to_dir, render_suite_markdown,
)
from je_web_runner.utils.exploratory_ai.explorer import (
    ExploratoryAiError, ActionKind, InteractiveElement, PageObservation, PlannedAction, BugSignal,
    ExplorationReport, PageObserver, ActionPlanner, RandomPlanner, Explorer,
)
from je_web_runner.utils.failure_auto_tag.tag import (
    FailureAutoTagError, FailureBundle as FailureAutoTagFailureBundle, Tag, heuristic_tags, llm_tags, merge_tags,
    assert_tagged_with,
)
from je_web_runner.utils.failure_narrator.narrator import (
    FailureNarratorError, FailureBundle as FailureNarratorFailureBundle, load_bundle_dir, NarratorClient,
    build_prompt as failure_narrator_build_prompt, NarrationReport,
    parse_response as failure_narrator_parse_response, narrate,
)
from je_web_runner.utils.failure_triage.triage import (
    FailureTriageError, TriageSignals, extract_signals_from_bundle, TriageReport, triage_failure, triage_bundle,
    render_markdown as failure_triage_render_markdown, save_report,
)
from je_web_runner.utils.hallucination_probe.probe import (
    HallucinationProbeError, Probe, ProbeResult, ProbeReport, run_probes, assert_hallucination_rate_under,
)
from je_web_runner.utils.llm_token_cost_tracker.tracker import (
    LlmTokenCostError, CallRecord, Tally, compute_cost, tally, tally_by_test, assert_under_budget, top_spenders,
)
from je_web_runner.utils.locator_hardener.hardener import (
    LocatorHardenerError, LocatorStrategy, FragileLocator, FragilityScore, score_fragility, HardenerClient,
    build_prompt as locator_hardener_build_prompt, LocatorSuggestion, parse_suggestions, harden,
)
from je_web_runner.utils.multimodal_qa.qa import (
    MultimodalQaError, Verdict, QaRequest, QaResponse, VisionClient, build_prompt as multimodal_qa_build_prompt,
    parse_response as multimodal_qa_parse_response, ask, ask_path, assert_passes,
)
from je_web_runner.utils.pr_title_generator.generate import (
    PrTitleGeneratorError, DiffStat, suggest_title, suggest_title_with_llm, assert_conventional,
)
from je_web_runner.utils.prompt_drift_monitor.monitor import (
    PromptDriftError, BaselineSample, Baseline, capture_baseline, save_baseline, load_baseline, DriftFinding,
    DriftReport, check_drift, assert_no_drift,
)
from je_web_runner.utils.prompt_injection_scanner.scanner import (
    PromptInjectionScannerError, Severity, Payload, LlmClient, Finding, ScanReport, scan, assert_no_leaks,
)
from je_web_runner.utils.rag_grounding_assert.grounding import (
    RagGroundingError, Chunk, RagAnswer, assert_citations_in_retrieved, assert_min_citations,
    lexical_overlap_score, assert_grounded, find_unsupported_claims, assert_no_hallucination,
)
from je_web_runner.utils.story_to_actions.generator import (
    StoryToActionsError, FigmaHint, StoryPrompt, StoryClient, build_prompt_text, generate_actions,
    validate_actions, write_actions_json,
)
from je_web_runner.utils.streaming_chat_assert.stream import (
    StreamingChatAssertError, TokenDelta, parse_deltas, assemble, time_to_first_token, max_inter_token_gap_ms,
    assert_ttft_under, assert_no_stall, assert_assembled_contains, assert_utf8_clean, assert_no_dup_or_oos,
)
from je_web_runner.utils.test_dedup_ai.dedup import (
    TestDedupError, ActionFile, load_dir, DuplicateCluster, structural_clusters, semantic_clusters,
    clusters_markdown, stable_fingerprint,
)
from je_web_runner.utils.test_self_describe.describe import (
    SelfDescribeError, StepSummary, summarise, describe, assert_mentions,
)
from je_web_runner.utils.tool_call_assert.tool import (
    ToolCallAssertError, ToolCall, parse_calls, assert_called, assert_not_called, assert_args_match_schema,
    assert_call_order,
)
from je_web_runner.utils.walkthrough_docs.generator import (
    WalkthroughError, WalkthroughStep, Walkthrough, collect_steps, narrate_steps,
    render_markdown as walkthrough_docs_render_markdown, render_confluence, build_walkthrough, save_walkthrough,
)

__all__ = [
    "LLMAssistError", "set_llm_callable", "has_llm_callable", "suggest_locator", "generate_actions_from_prompt",
    "llm_self_heal_locator", "explain_failure", "TestAutoRepairError", "collect_git_diff", "RepairPlan",
    "propose_repair", "repair_from_bundle", "apply_repair", "render_repair_markdown", "EdgeCaseGeneratorError",
    "EdgeCaseCategory", "EdgeCase", "EdgeCaseSuite", "generate_edge_cases", "generate_edge_cases_from_file",
    "write_suite_to_dir", "render_suite_markdown", "ExploratoryAiError", "ActionKind", "InteractiveElement",
    "PageObservation", "PlannedAction", "BugSignal", "ExplorationReport", "PageObserver", "ActionPlanner",
    "RandomPlanner", "Explorer", "FailureAutoTagError", "FailureAutoTagFailureBundle", "Tag", "heuristic_tags",
    "llm_tags", "merge_tags", "assert_tagged_with", "FailureNarratorError", "FailureNarratorFailureBundle",
    "load_bundle_dir", "NarratorClient", "failure_narrator_build_prompt", "NarrationReport",
    "failure_narrator_parse_response", "narrate", "FailureTriageError", "TriageSignals",
    "extract_signals_from_bundle", "TriageReport", "triage_failure", "triage_bundle",
    "failure_triage_render_markdown", "save_report", "HallucinationProbeError", "Probe", "ProbeResult",
    "ProbeReport", "run_probes", "assert_hallucination_rate_under", "LlmTokenCostError", "CallRecord", "Tally",
    "compute_cost", "tally", "tally_by_test", "assert_under_budget", "top_spenders", "LocatorHardenerError",
    "LocatorStrategy", "FragileLocator", "FragilityScore", "score_fragility", "HardenerClient",
    "locator_hardener_build_prompt", "LocatorSuggestion", "parse_suggestions", "harden", "MultimodalQaError",
    "Verdict", "QaRequest", "QaResponse", "VisionClient", "multimodal_qa_build_prompt",
    "multimodal_qa_parse_response", "ask", "ask_path", "assert_passes", "PrTitleGeneratorError", "DiffStat",
    "suggest_title", "suggest_title_with_llm", "assert_conventional", "PromptDriftError", "BaselineSample",
    "Baseline", "capture_baseline", "save_baseline", "load_baseline", "DriftFinding", "DriftReport", "check_drift",
    "assert_no_drift", "PromptInjectionScannerError", "Severity", "Payload", "LlmClient", "Finding", "ScanReport",
    "scan", "assert_no_leaks", "RagGroundingError", "Chunk", "RagAnswer", "assert_citations_in_retrieved",
    "assert_min_citations", "lexical_overlap_score", "assert_grounded", "find_unsupported_claims",
    "assert_no_hallucination", "StoryToActionsError", "FigmaHint", "StoryPrompt", "StoryClient",
    "build_prompt_text", "generate_actions", "validate_actions", "write_actions_json", "StreamingChatAssertError",
    "TokenDelta", "parse_deltas", "assemble", "time_to_first_token", "max_inter_token_gap_ms", "assert_ttft_under",
    "assert_no_stall", "assert_assembled_contains", "assert_utf8_clean", "assert_no_dup_or_oos", "TestDedupError",
    "ActionFile", "load_dir", "DuplicateCluster", "structural_clusters", "semantic_clusters", "clusters_markdown",
    "stable_fingerprint", "SelfDescribeError", "StepSummary", "summarise", "describe", "assert_mentions",
    "ToolCallAssertError", "ToolCall", "parse_calls", "assert_called", "assert_not_called",
    "assert_args_match_schema", "assert_call_order", "WalkthroughError", "WalkthroughStep", "Walkthrough",
    "collect_steps", "narrate_steps", "walkthrough_docs_render_markdown", "render_confluence", "build_walkthrough",
    "save_walkthrough",
]
