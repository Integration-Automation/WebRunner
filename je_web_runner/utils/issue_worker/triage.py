"""Explainable, host-owned intake classification and advisory automation suitability."""
from __future__ import annotations

import re
from typing import Any

from je_web_runner.utils.issue_worker.types import IssueSnapshot, IssueWorkerConfig

_KINDS = {
    "bug": {"bug", "bugfix", "fix", "錯誤", "错误", "修正", "修复"},
    "feature": {"feature", "enhancement", "功能", "新增"},
    "refactor": {"refactor", "refactoring", "重構", "重构"},
    "test": {"test", "tests", "testing", "測試", "测试"},
    "documentation": {"doc", "docs", "documentation", "文件", "文檔", "文档"},
}
MANUAL_LABELS = {"automation-manual", "automation-blocked"}


def assess_issue(snapshot: IssueSnapshot, config: IssueWorkerConfig) -> dict[str, Any]:
    """Use labels for authority/priority; body heuristics only advise and never change tool permissions."""
    labels = {label.casefold().strip() for label in snapshot.labels}
    priorities = {name.casefold().strip(): value for name, value in config.priority_labels.items()}
    matched = sorted(labels & priorities.keys())
    priority = max((priorities[label] for label in matched), default=50)
    kind, basis = _classify(snapshot.title, labels)
    body = snapshot.body.strip()
    signals = []
    score = 30
    if len(body) >= 40:
        score += 20
        signals.append("description_present")
    if re.search(r"acceptance|expected|驗收|验收|預期|预期|- \[[ xX]\]", body, re.IGNORECASE):
        score += 25
        signals.append("acceptance_described")
    if re.search(r"test|pytest|測試|测试|重現|复现|reproduce", body, re.IGNORECASE):
        score += 15
        signals.append("test_or_reproduction_described")
    if re.search(r"[\w/-]+\.(py|html|js|rst|md)\b", body):
        score += 10
        signals.append("source_paths_present")
    manual = sorted(labels & MANUAL_LABELS)
    reasons = ["manual_label:" + label for label in manual]
    if len(body) < 40:
        reasons.append("brief_requirements")
    if len(body) > 50000:
        score = min(score, 40)
        reasons.append("large_requirements_need_decomposition")
    return {"kind": kind, "classification_basis": basis, "priority": priority,
            "priority_labels": matched, "suitable": not manual, "suitability_score": score,
            "signals": signals, "reasons": reasons, "score_is_advisory": True}


def _classify(title: str, labels: set[str]) -> tuple[str, str]:
    for kind, names in _KINDS.items():
        if labels & names:
            return kind, "label"
    prefix = re.split(r"[:：\s(]", title.casefold(), maxsplit=1)[0]
    for kind, names in _KINDS.items():
        if prefix in names:
            return kind, "title_prefix"
    return "unknown", "insufficient_signal"
