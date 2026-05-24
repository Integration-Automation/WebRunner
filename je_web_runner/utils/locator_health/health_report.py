"""
Locator 健康度報告 + 自動升級建議。

Project-wide locator audit built on top of
:mod:`je_web_runner.utils.linter.locator_strength`:

* Walk a directory of action JSON files, score every locator.
* Combine static scores with runtime ``FallbackHitTracker`` counts so
  locators that *actually* trigger self-healing get flagged loudest.
* Suggest upgrades: prefer ``data-testid`` / ``ID`` over CSS over deep
  XPath. The upgrade function is conservative — it never silently rewrites
  files; you have to call :func:`apply_upgrades` to mutate an action list.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.linter.locator_strength import (
    LocatorStrengthError,
    score_locator,
)
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class LocatorHealthError(WebRunnerException):
    """Raised on scan / report / upgrade failures."""


# ---------- runtime tracker ---------------------------------------------

class FallbackHitTracker:
    """
    記錄 self-healing fallback 觸發次數，供報告交叉比對。
    Thread-safe counter that self-healing callers can poke whenever a
    fallback locator matches instead of the primary. The report can then
    rank weak locators by how often they actually misfire.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: Dict[str, int] = {}
        self._fallback_used: Dict[str, int] = {}

    def track_primary(self, name: str) -> None:
        with self._lock:
            self._hits[name] = self._hits.get(name, 0) + 1

    def track_fallback(self, name: str) -> None:
        with self._lock:
            self._hits[name] = self._hits.get(name, 0) + 1
            self._fallback_used[name] = self._fallback_used.get(name, 0) + 1

    def stats(self) -> Dict[str, Dict[str, int]]:
        with self._lock:
            return {
                name: {
                    "hits": self._hits.get(name, 0),
                    "fallback_used": self._fallback_used.get(name, 0),
                }
                for name in self._hits
            }

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()
            self._fallback_used.clear()


fallback_hit_tracker = FallbackHitTracker()


# ---------- scanning -----------------------------------------------------

@dataclass
class LocatorFinding:
    """One locator discovered while scanning an action file."""

    file_path: str
    action_index: int
    strategy: str
    value: str
    score: int
    reasons: List[str] = field(default_factory=list)
    name: Optional[str] = None
    hits: int = 0
    fallback_used: int = 0

    @property
    def fallback_rate(self) -> float:
        return (self.fallback_used / self.hits) if self.hits else 0.0

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["fallback_rate"] = round(self.fallback_rate, 4)
        return out


def _walk_actions(payload: Any) -> Iterable[List[Any]]:
    """Yield every action list inside ``payload`` (top-level list or nested)."""
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, list) and item and isinstance(item[0], str):
                yield item


def _extract_locator(action: List[Any]) -> Optional[Dict[str, Any]]:
    if len(action) < 2:
        return None
    kwargs = None
    if len(action) >= 3 and isinstance(action[2], dict):
        kwargs = action[2]
    elif isinstance(action[1], dict):
        kwargs = action[1]
    else:
        return None
    strategy = kwargs.get("object_type") or kwargs.get("strategy")
    value = kwargs.get("test_object_name") or kwargs.get("value")
    name = kwargs.get("element_name") or kwargs.get("name") or kwargs.get("test_object_name")
    if strategy is None or value is None:
        return None
    return {"strategy": str(strategy), "value": str(value), "name": str(name) if name else None}


def scan_action_file(file_path: Union[str, Path]) -> List[LocatorFinding]:
    """Score every locator inside one action JSON file."""
    path = Path(file_path)
    if not path.is_file():
        raise LocatorHealthError(f"action file not found: {path}")
    try:
        with open(path, encoding="utf-8") as fp:
            payload = json.load(fp)
    except (OSError, ValueError) as error:
        raise LocatorHealthError(f"cannot parse {path}: {error!r}") from error

    findings: List[LocatorFinding] = []
    hit_stats = fallback_hit_tracker.stats()
    for index, action in enumerate(_walk_actions(payload)):
        locator = _extract_locator(action)
        if locator is None:
            continue
        try:
            score = score_locator(locator["strategy"], locator["value"])
        except LocatorStrengthError as error:
            web_runner_logger.warning(
                f"scan_action_file: cannot score {path}#{index}: {error!r}"
            )
            continue
        name = locator["name"]
        hits_info = hit_stats.get(name or "", {"hits": 0, "fallback_used": 0})
        findings.append(LocatorFinding(
            file_path=str(path),
            action_index=index,
            strategy=score.strategy,
            value=score.value,
            score=score.score,
            reasons=list(score.reasons),
            name=name,
            hits=hits_info["hits"],
            fallback_used=hits_info["fallback_used"],
        ))
    return findings


def scan_project(
    root: Union[str, Path],
    pattern: str = "**/*.json",
) -> List[LocatorFinding]:
    """
    掃整個專案的 action JSON、收集所有 locator finding。
    Walk ``root`` for files matching ``pattern`` and score every locator.
    Files that don't decode as JSON are skipped with a warning so a stray
    config file doesn't kill the whole scan.
    """
    root = Path(root)
    if not root.is_dir():
        raise LocatorHealthError(f"project root is not a directory: {root}")
    findings: List[LocatorFinding] = []
    for file_path in sorted(root.glob(pattern)):
        if not file_path.is_file():
            continue
        try:
            findings.extend(scan_action_file(file_path))
        except LocatorHealthError as error:
            web_runner_logger.warning(f"scan_project skip {file_path}: {error!r}")
    return findings


# ---------- report -------------------------------------------------------

@dataclass
class LocatorHealthReport:
    """Aggregate health report rendered for humans or CI dashboards."""

    total: int
    weak: int
    strong: int
    average_score: float
    findings: List[LocatorFinding] = field(default_factory=list)
    weakest: List[LocatorFinding] = field(default_factory=list)
    fallback_offenders: List[LocatorFinding] = field(default_factory=list)
    threshold: int = 60

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "weak": self.weak,
            "strong": self.strong,
            "average_score": self.average_score,
            "threshold": self.threshold,
            "findings": [f.to_dict() for f in self.findings],
            "weakest": [f.to_dict() for f in self.weakest],
            "fallback_offenders": [f.to_dict() for f in self.fallback_offenders],
        }


def build_health_report(
    findings: Iterable[LocatorFinding],
    *,
    threshold: int = 60,
    weakest_limit: int = 10,
    fallback_min_rate: float = 0.2,
) -> LocatorHealthReport:
    """
    把 finding list 整合成 report，包含弱定位排行 + fallback 觸發排行。
    Aggregate findings into a report with two ranked sub-lists:

    * ``weakest`` — locators with the lowest static scores.
    * ``fallback_offenders`` — locators whose self-healing fallback fired
      at least ``fallback_min_rate`` of the time at runtime (only matters
      if callers have been poking ``fallback_hit_tracker``).
    """
    materialised = list(findings)
    total = len(materialised)
    if total == 0:
        return LocatorHealthReport(
            total=0, weak=0, strong=0, average_score=0.0, threshold=threshold,
        )
    weak = sum(1 for f in materialised if f.score < threshold)
    strong = total - weak
    avg = sum(f.score for f in materialised) / total
    weakest = sorted(materialised, key=lambda f: f.score)[:weakest_limit]
    fallback_offenders = sorted(
        (f for f in materialised if f.fallback_rate >= fallback_min_rate),
        key=lambda f: (-f.fallback_rate, f.score),
    )
    return LocatorHealthReport(
        total=total,
        weak=weak,
        strong=strong,
        average_score=round(avg, 2),
        findings=materialised,
        weakest=weakest,
        fallback_offenders=fallback_offenders,
        threshold=threshold,
    )


# ---------- upgrade suggestions ------------------------------------------

@dataclass
class UpgradeSuggestion:
    """A proposed replacement for one weak locator."""

    file_path: str
    action_index: int
    from_strategy: str
    from_value: str
    to_strategy: str
    to_value: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_STRATEGY_PRIORITY: Dict[str, int] = {
    "ID": 100, "id": 100,
    "NAME": 70, "name": 70,
    "CSS_SELECTOR": 75, "css selector": 75, "css": 75,
    "XPATH": 55, "xpath": 55,
    "CLASS_NAME": 45, "class name": 45,
    "TAG_NAME": 25, "tag name": 25,
    "LINK_TEXT": 35, "link text": 35,
    "PARTIAL_LINK_TEXT": 30, "partial link text": 30,
}


def _suggest_for_xpath(finding: LocatorFinding) -> Optional[UpgradeSuggestion]:
    """Heuristic: if an XPath anchors on ``@id='X'``, suggest using ID directly."""
    value = finding.value
    # //*[@id='foo'] or //tag[@id="foo"]
    import re as _re
    match = _re.search(r"@id\s*=\s*['\"]([^'\"]+)['\"]", value)
    if match:
        new_value = match.group(1)
        return UpgradeSuggestion(
            file_path=finding.file_path,
            action_index=finding.action_index,
            from_strategy=finding.strategy,
            from_value=value,
            to_strategy="ID",
            to_value=new_value,
            rationale=f"XPath anchored on @id={new_value!r}; ID strategy is stabler",
        )
    match = _re.search(r"@data-testid\s*=\s*['\"]([^'\"]+)['\"]", value)
    if match:
        return UpgradeSuggestion(
            file_path=finding.file_path,
            action_index=finding.action_index,
            from_strategy=finding.strategy,
            from_value=value,
            to_strategy="CSS_SELECTOR",
            to_value=f"[data-testid='{match.group(1)}']",
            rationale="XPath uses data-testid; CSS selector reads cleaner",
        )
    return None


def _suggest_for_css(finding: LocatorFinding) -> Optional[UpgradeSuggestion]:
    """Heuristic: if a CSS selector anchors on ``#id`` alone, suggest ID."""
    value = finding.value.strip()
    if value.startswith("#") and " " not in value and ">" not in value:
        return UpgradeSuggestion(
            file_path=finding.file_path,
            action_index=finding.action_index,
            from_strategy=finding.strategy,
            from_value=value,
            to_strategy="ID",
            to_value=value[1:],
            rationale="CSS selector is a single #id; switch to ID strategy",
        )
    return None


def suggest_upgrade(finding: LocatorFinding) -> Optional[UpgradeSuggestion]:
    """
    回傳 finding 的一個升級建議；找不到合理建議回 None。
    Look for a structural pattern that points at a better strategy. Returns
    None when the finding is already strong or we can't find a clear win.
    """
    strategy = finding.strategy
    if strategy in {"XPATH", "xpath"}:
        return _suggest_for_xpath(finding)
    if strategy in {"CSS_SELECTOR", "css selector", "css"}:
        return _suggest_for_css(finding)
    return None


def suggest_upgrades(
    findings: Iterable[LocatorFinding],
    *,
    only_below: Optional[int] = None,
) -> List[UpgradeSuggestion]:
    """
    對一批 finding 收集所有可行的升級建議。
    Walk a finding list and return every upgrade suggestion. Pass
    ``only_below`` to skip findings whose static score is already above
    a chosen threshold.
    """
    suggestions: List[UpgradeSuggestion] = []
    for finding in findings:
        if only_below is not None and finding.score >= only_below:
            continue
        suggestion = suggest_upgrade(finding)
        if suggestion is not None:
            suggestions.append(suggestion)
    return suggestions


def apply_upgrades(  # NOSONAR S3776 — cohesive logic; planned refactor in follow-up
    actions: List[Any],
    suggestions: Iterable[UpgradeSuggestion],
) -> List[Any]:
    """
    根據 suggestion 把 action list 內的 locator 改寫，回傳新的 list。
    Non-mutating: returns a deep-copied action list with the chosen
    suggestions applied. Suggestions whose ``action_index`` is out of range
    are skipped with a warning.
    """
    import copy as _copy
    new_actions = _copy.deepcopy(actions)
    by_index: Dict[int, UpgradeSuggestion] = {}
    for s in suggestions:
        by_index[s.action_index] = s
    for index, action in enumerate(new_actions):
        suggestion = by_index.get(index)
        if suggestion is None:
            continue
        if not isinstance(action, list) or len(action) < 2:
            continue
        if len(action) >= 3 and isinstance(action[2], dict):
            kwargs = action[2]
        elif isinstance(action[1], dict):
            kwargs = action[1]
        else:
            kwargs = None
        if kwargs is None:
            continue
        if "object_type" in kwargs:
            kwargs["object_type"] = suggestion.to_strategy
        if "strategy" in kwargs:
            kwargs["strategy"] = suggestion.to_strategy
        if "test_object_name" in kwargs:
            kwargs["test_object_name"] = suggestion.to_value
        if "value" in kwargs:
            kwargs["value"] = suggestion.to_value
    return new_actions


# ---------- rendering ----------------------------------------------------

def render_health_markdown(report: LocatorHealthReport) -> str:
    """Render the report as markdown suitable for PR comments."""
    pieces = [
        "## Locator health report",
        "",
        f"- **Total locators:** {report.total}",
        f"- **Weak (< {report.threshold}):** {report.weak}",
        f"- **Strong:** {report.strong}",
        f"- **Average score:** {report.average_score}",
        "",
    ]
    if report.weakest:
        pieces.append("### Weakest locators")
        pieces.append("| File | Idx | Strategy | Value | Score | Reasons |")
        pieces.append("|------|-----|----------|-------|-------|---------|")
        for f in report.weakest:
            value = (f.value[:60] + "…") if len(f.value) > 60 else f.value
            pieces.append(
                f"| `{Path(f.file_path).name}` | {f.action_index} | `{f.strategy}` "
                f"| `{value}` | {f.score} | {'; '.join(f.reasons) or '—'} |"
            )
        pieces.append("")
    if report.fallback_offenders:
        pieces.append("### Self-healing offenders (fallback fired at runtime)")
        pieces.append("| File | Strategy | Hits | Fallback used | Rate |")
        pieces.append("|------|----------|------|---------------|------|")
        for f in report.fallback_offenders:
            pieces.append(
                f"| `{Path(f.file_path).name}` | `{f.strategy}` | {f.hits} | "
                f"{f.fallback_used} | {f.fallback_rate:.0%} |"
            )
        pieces.append("")
    return "\n".join(pieces).rstrip() + "\n"


def save_health_report(
    report: LocatorHealthReport,
    output_path: Union[str, Path],
) -> Path:
    """Persist the JSON form of the report next to a CI artifact."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(report.to_dict(), fp, ensure_ascii=False, indent=2)
    web_runner_logger.info(f"save_health_report: wrote {path}")
    return path
