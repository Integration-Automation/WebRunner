"""Test impact analysis: action JSON files → locator/url/template usage map."""
from je_web_runner.utils.impact_analysis.indexer import (
    ImpactAnalysisError,
    ImpactIndex,
    affected_action_files,
    build_index,
)

__all__ = [
    "ImpactAnalysisError",
    "ImpactIndex",
    "affected_action_files",
    "build_index",
]
