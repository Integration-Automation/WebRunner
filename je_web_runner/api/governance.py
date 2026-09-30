"""Facade: Test governance: flakes, quarantine, ownership, debt, cost, risk, gates and triage."""
from je_web_runner.utils.action_refactor_suggester.suggest import (
    ActionRefactorSuggesterError, Severity, Suggestion, analyze,
    report_markdown as action_refactor_suggester_report_markdown, assert_no_warns_or_errors,
)
from je_web_runner.utils.bug_repro_stability.stability import (
    BugReproStabilityError, ReproCategory, RunOutcome, StabilityReport, repeat, assert_deterministic,
    assert_min_repro_pct, report_markdown as bug_repro_stability_report_markdown,
)
from je_web_runner.utils.commit_msg_trigger.trigger import (
    CommitMsgTriggerError, TriggerPlan, parse, should_run_job, assigned_shard, assert_no_skip,
)
from je_web_runner.utils.failure_cluster_dbscan.cluster import (
    FailureClusterDbscanError, FailureRecord, Cluster, cluster, cluster_summary, assert_root_causes_at_most,
)
from je_web_runner.utils.flake_detector.detector import (
    FlakeDetectorError, FlakeScore, compute_flake_scores, compute_flake_scores_from_runs,
    flaky_paths as flake_detector_flaky_paths, QuarantineEntry, QuarantineRegistry, quarantine_flaky,
    release_if_stable, flaky_quarantine, quarantine_report_markdown,
)
from je_web_runner.utils.flakiness_graveyard.graveyard import (
    FlakinessGraveyardError, Status as FlakinessGraveyardStatus, GraveEntry, register_flake, revive,
    due_for_burial, bury, load as flakiness_graveyard_load, save as flakiness_graveyard_save,
)
from je_web_runner.utils.git_bisect_flake.bisect import (
    GitBisectFlakeError, LedgerEntry, load_ledger, BisectResult, bisect_from_ledger, bisect_with_probe,
    report_markdown as git_bisect_flake_report_markdown,
)
from je_web_runner.utils.mutation_testing.mutator import (
    MutationTestingError, MutationType, Mutation, MutationResult, MutationScore, generate_mutations,
    apply_mutation, run_mutation_testing, run_mutation_testing_on_file, render_mutation_markdown, assert_min_score,
)
from je_web_runner.utils.pr_risk_score.scorer import (
    PrRiskScoreError, PrSignals, RiskWeights, RiskReport, score_pr,
    report_markdown as pr_risk_score_report_markdown, aggregate_signals,
)
from je_web_runner.utils.pre_merge_gate_dsl.gate import (
    PreMergeGateDslError, PrFacts, Rule as PreMergeGateDslRule, GateResult, parse_rules, evaluate,
    assert_gate_passes,
)
from je_web_runner.utils.quarantine_age_report.report import (
    QuarantineAgeReportError, EscalationTier, AgedEntry, AgeReport, age_entries, build_report, load_and_age,
    report_markdown as quarantine_age_report_report_markdown, assert_no_abandoned,
)
from je_web_runner.utils.repro_minimizer.minimizer import (
    ReproMinimizerError, MinimizationResult, minimize, assert_minimized,
    report_markdown as repro_minimizer_report_markdown,
)
from je_web_runner.utils.run_ledger.classifier import (
    ClassifierError, classify_error, classify, classify_failures,
)
from je_web_runner.utils.run_ledger.flaky import (
    FlakyDetectorError, flakiness_stats, flaky_paths as run_ledger_flaky_paths,
)
from je_web_runner.utils.run_ledger.ledger import (
    LedgerError, record_run, latest_status, failed_files, passed_files, clear_ledger,
)
from je_web_runner.utils.sla_tracker.tracker import (
    SlaTrackerError, SuiteRun, load_runs as sla_tracker_load_runs, SlaTarget, BucketResult, SlaReport, compute_sla,
    report_markdown as sla_tracker_report_markdown, assert_meets_sla,
)
from je_web_runner.utils.snapshot_diff_approval.approval import (
    SnapshotDiffApprovalError, Status as SnapshotDiffApprovalStatus, SnapshotEntry, DiffResult,
    load as snapshot_diff_approval_load, save as snapshot_diff_approval_save, capture, approve, reject,
    list_pending, assert_no_pending,
)
from je_web_runner.utils.test_blame_owner.owner import (
    BlameOwnerError, BlameLine, CodeownersRule as TestBlameOwnerCodeownersRule,
    parse_codeowners as test_blame_owner_parse_codeowners, owners_from_codeowners, owners_from_blame, OwnerVerdict,
    resolve_owner, assert_has_owner,
)
from je_web_runner.utils.test_categorizer.categorizer import (
    TestCategorizerError, Rule as TestCategorizerRule, CategoryAssignment, categorize_actions, categorize_file,
    categorize_dir, TagDistribution, aggregate,
)
from je_web_runner.utils.test_cost_estimator.estimator import (
    TestCostEstimatorError, RateCard, rate_card_index, RunRow, load_runs as test_cost_estimator_load_runs,
    CostBreakdown, CostEstimate, estimate_runs, estimate_markdown,
)
from je_web_runner.utils.test_debt_dashboard.debt import (
    TestDebtDashboardError, DebtKind, DebtItem, DebtReport, CodeownersIndex,
    parse_codeowners as test_debt_dashboard_parse_codeowners, scan_python_file, scan_action_json, scan_directory,
    assert_under_age_limit, report_markdown as test_debt_dashboard_report_markdown,
)
from je_web_runner.utils.test_dup_dry.dedup import (
    DupDryError, DupSpec, DuplicateGroup, find_duplicates, PrefixOverlap, find_prefix_overlap,
    assert_no_duplicates,
)
from je_web_runner.utils.test_management.jira_client import (
    JiraError, jira_create_issue, jira_create_failure_issues,
)
from je_web_runner.utils.test_management.testrail_client import (
    TestRailError, testrail_send_results, testrail_results_from_pairs, testrail_close_run,
)
from je_web_runner.utils.test_naming_lint.lint import (
    NamingLintError, Convention, NamingFinding, lint_test_name, lint_many, assert_clean,
)
from je_web_runner.utils.test_owners_map.owners import (
    TestOwnersMapError, CodeownersRule as TestOwnersMapCodeownersRule, OwnersFile,
    parse_codeowners as test_owners_map_parse_codeowners, load_codeowners_file, OwnersMap, load_overrides,
    OwnerAudit, audit_unowned, assert_no_unowned, audit_markdown,
)
from je_web_runner.utils.test_roi_scorer.score import (
    RoiScorerError, RoiMetrics, Weights, RoiScore, score_one, score_many, removal_candidates,
)
from je_web_runner.utils.test_scheduler.scheduler import (
    TestSchedulerError, TestCandidate, Schedule, value_of, value_density, schedule_tests,
    build_candidates_from_ledger, render_schedule_markdown,
)

__all__ = [
    "ActionRefactorSuggesterError", "Severity", "Suggestion", "analyze",
    "action_refactor_suggester_report_markdown", "assert_no_warns_or_errors", "BugReproStabilityError",
    "ReproCategory", "RunOutcome", "StabilityReport", "repeat", "assert_deterministic", "assert_min_repro_pct",
    "bug_repro_stability_report_markdown", "CommitMsgTriggerError", "TriggerPlan", "parse", "should_run_job",
    "assigned_shard", "assert_no_skip", "FailureClusterDbscanError", "FailureRecord", "Cluster", "cluster",
    "cluster_summary", "assert_root_causes_at_most", "FlakeDetectorError", "FlakeScore", "compute_flake_scores",
    "compute_flake_scores_from_runs", "flake_detector_flaky_paths", "QuarantineEntry", "QuarantineRegistry",
    "quarantine_flaky", "release_if_stable", "flaky_quarantine", "quarantine_report_markdown",
    "FlakinessGraveyardError", "FlakinessGraveyardStatus", "GraveEntry", "register_flake", "revive",
    "due_for_burial", "bury", "flakiness_graveyard_load", "flakiness_graveyard_save", "GitBisectFlakeError",
    "LedgerEntry", "load_ledger", "BisectResult", "bisect_from_ledger", "bisect_with_probe",
    "git_bisect_flake_report_markdown", "MutationTestingError", "MutationType", "Mutation", "MutationResult",
    "MutationScore", "generate_mutations", "apply_mutation", "run_mutation_testing",
    "run_mutation_testing_on_file", "render_mutation_markdown", "assert_min_score", "PrRiskScoreError",
    "PrSignals", "RiskWeights", "RiskReport", "score_pr", "pr_risk_score_report_markdown", "aggregate_signals",
    "PreMergeGateDslError", "PrFacts", "PreMergeGateDslRule", "GateResult", "parse_rules", "evaluate",
    "assert_gate_passes", "QuarantineAgeReportError", "EscalationTier", "AgedEntry", "AgeReport", "age_entries",
    "build_report", "load_and_age", "quarantine_age_report_report_markdown", "assert_no_abandoned",
    "ReproMinimizerError", "MinimizationResult", "minimize", "assert_minimized", "repro_minimizer_report_markdown",
    "ClassifierError", "classify_error", "classify", "classify_failures", "FlakyDetectorError", "flakiness_stats",
    "run_ledger_flaky_paths", "LedgerError", "record_run", "latest_status", "failed_files", "passed_files",
    "clear_ledger", "SlaTrackerError", "SuiteRun", "sla_tracker_load_runs", "SlaTarget", "BucketResult",
    "SlaReport", "compute_sla", "sla_tracker_report_markdown", "assert_meets_sla", "SnapshotDiffApprovalError",
    "SnapshotDiffApprovalStatus", "SnapshotEntry", "DiffResult", "snapshot_diff_approval_load",
    "snapshot_diff_approval_save", "capture", "approve", "reject", "list_pending", "assert_no_pending",
    "BlameOwnerError", "BlameLine", "TestBlameOwnerCodeownersRule", "test_blame_owner_parse_codeowners",
    "owners_from_codeowners", "owners_from_blame", "OwnerVerdict", "resolve_owner", "assert_has_owner",
    "TestCategorizerError", "TestCategorizerRule", "CategoryAssignment", "categorize_actions", "categorize_file",
    "categorize_dir", "TagDistribution", "aggregate", "TestCostEstimatorError", "RateCard", "rate_card_index",
    "RunRow", "test_cost_estimator_load_runs", "CostBreakdown", "CostEstimate", "estimate_runs",
    "estimate_markdown", "TestDebtDashboardError", "DebtKind", "DebtItem", "DebtReport", "CodeownersIndex",
    "test_debt_dashboard_parse_codeowners", "scan_python_file", "scan_action_json", "scan_directory",
    "assert_under_age_limit", "test_debt_dashboard_report_markdown", "DupDryError", "DupSpec", "DuplicateGroup",
    "find_duplicates", "PrefixOverlap", "find_prefix_overlap", "assert_no_duplicates", "JiraError",
    "jira_create_issue", "jira_create_failure_issues", "TestRailError", "testrail_send_results",
    "testrail_results_from_pairs", "testrail_close_run", "NamingLintError", "Convention", "NamingFinding",
    "lint_test_name", "lint_many", "assert_clean", "TestOwnersMapError", "TestOwnersMapCodeownersRule",
    "OwnersFile", "test_owners_map_parse_codeowners", "load_codeowners_file", "OwnersMap", "load_overrides",
    "OwnerAudit", "audit_unowned", "assert_no_unowned", "audit_markdown", "RoiScorerError", "RoiMetrics",
    "Weights", "RoiScore", "score_one", "score_many", "removal_candidates", "TestSchedulerError", "TestCandidate",
    "Schedule", "value_of", "value_density", "schedule_tests", "build_candidates_from_ledger",
    "render_schedule_markdown",
]
