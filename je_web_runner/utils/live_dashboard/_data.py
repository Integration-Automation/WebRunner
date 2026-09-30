"""
儀表板的資料來源 / Loaders for the dashboard's data sources.

Every call re-reads its file, so the dashboard always shows the latest state.
Missing or malformed files load as empty (and log a warning) rather than failing
the page.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.flake_detector.detector import (
    QuarantineRegistry,
    compute_flake_scores_from_runs,
)
from je_web_runner.utils.live_dashboard._config import DashboardConfig
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


def _read_ledger_runs(ledger_path: Path | None) -> list[dict[str, Any]]:
    """Every run record in the ledger, oldest first; empty when the file is missing or malformed."""
    if ledger_path is None or not ledger_path.exists():
        return []
    try:
        with open(ledger_path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, ValueError) as error:
        web_runner_logger.warning(f"dashboard ledger read: {error!r}")
        return []
    runs = data.get("runs") if isinstance(data, dict) else None
    if not isinstance(runs, list):
        return []
    return [run for run in runs if isinstance(run, dict)]


def _recent(runs: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return runs[-limit:][::-1]


def _flake_entries(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        scores = compute_flake_scores_from_runs(runs)
    except (WebRunnerException, ValueError) as error:
        web_runner_logger.warning(f"dashboard flake scores: {error!r}")
        return []
    entries = [s.to_dict() for s in scores.values()]
    entries.sort(key=lambda e: (-e["flake_score"], e["path"]))
    return entries


def _load_runs(ledger_path: Path | None, limit: int = 50) -> list[dict[str, Any]]:
    return _recent(_read_ledger_runs(ledger_path), limit)


def _load_flake_scores(ledger_path: Path | None) -> list[dict[str, Any]]:
    return _flake_entries(_read_ledger_runs(ledger_path))


def _load_quarantine(quarantine_path: Path | None) -> list[dict[str, Any]]:
    if quarantine_path is None or not quarantine_path.exists():
        return []
    try:
        registry = QuarantineRegistry(quarantine_path)
    except (WebRunnerException, ValueError, TypeError) as error:
        web_runner_logger.warning(f"dashboard _load_quarantine: {error!r}")
        return []
    return [e.to_dict() for e in registry.list()]


def _load_locator_report(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, ValueError) as error:
        web_runner_logger.warning(f"dashboard _load_locator_report: {error!r}")
        return {}


def _load_schedule(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, ValueError) as error:
        web_runner_logger.warning(f"dashboard _load_schedule: {error!r}")
        return {}


def _load_triage(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, ValueError) as error:
        web_runner_logger.warning(f"dashboard _load_triage: {error!r}")
        return {}


def build_summary(config: DashboardConfig) -> dict[str, Any]:
    """One-shot snapshot used by ``/`` and ``/api/summary``."""
    all_runs = _read_ledger_runs(config.ledger_path)
    runs = _recent(all_runs, 10_000)
    total = len(runs)
    passed = sum(1 for r in runs if r.get("passed"))
    failed = total - passed
    pass_rate = (passed / total) if total else 0.0
    flake_entries = _flake_entries(all_runs)
    flake_count = sum(1 for f in flake_entries if f.get("is_flaky"))
    quarantine = _load_quarantine(config.quarantine_path)
    locator_report = _load_locator_report(config.locator_findings_path)
    return {
        "total_runs": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(pass_rate, 4),
        "flaky_tests": flake_count,
        "quarantined_tests": len(quarantine),
        "weak_locators": locator_report.get("weak", 0) if isinstance(locator_report, dict) else 0,
        "average_locator_score": (
            locator_report.get("average_score", 0)
            if isinstance(locator_report, dict) else 0
        ),
    }
