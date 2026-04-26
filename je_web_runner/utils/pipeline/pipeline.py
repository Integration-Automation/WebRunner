"""
多階段 action 流水線：宣告式把 action JSON 檔組成 stages，每個 stage 可選 ``continue_on_failure``。
Multi-stage pipeline DSL. Each stage groups one or more action files
that run together; the next stage only fires if the previous stage
``status`` is in the configured ``required_status`` set. Stages can be
declared with ``continue_on_failure=True`` to act as collect-all gates
(linters, scanners) that don't short-circuit the pipeline.

The pipeline is JSON-serialisable so it diffs cleanly in PRs:

.. code-block:: json

    {
      "stages": [
        {"name": "lint",   "files": ["actions/*.json"], "continue_on_failure": true},
        {"name": "smoke",  "files": ["actions/smoke/*.json"]},
        {"name": "regression", "files": ["actions/full/*.json"],
         "required_status": ["passed"]}
      ]
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PipelineError(WebRunnerException):
    """Raised when pipeline definition or run input is invalid."""


@dataclass
class PipelineStage:
    name: str
    files: List[str]
    required_status: List[str] = field(default_factory=lambda: ["passed"])
    continue_on_failure: bool = False


@dataclass
class PipelineResult:
    stage_name: str
    status: str  # "passed" / "failed" / "skipped"
    file_results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class Pipeline:
    stages: List[PipelineStage] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"stages": [
            {
                "name": stage.name,
                "files": list(stage.files),
                "required_status": list(stage.required_status),
                "continue_on_failure": stage.continue_on_failure,
            }
            for stage in self.stages
        ]}


def load_pipeline(source: Union[str, Path, Dict[str, Any]]) -> Pipeline:
    """Load a pipeline definition from a path / JSON string / dict."""
    document = _coerce_pipeline_document(source)
    raw_stages = document.get("stages")
    if not isinstance(raw_stages, list) or not raw_stages:
        raise PipelineError("'stages' must be a non-empty list")
    stages: List[PipelineStage] = []
    seen: set = set()
    for index, entry in enumerate(raw_stages):
        stages.append(_parse_stage(index, entry, seen))
    return Pipeline(stages=stages)


def _coerce_pipeline_document(source: Union[str, Path, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(source, dict):
        document = source
    elif isinstance(source, (str, Path)):
        document = _load_pipeline_from_text(source)
    else:
        raise PipelineError(f"unsupported source type: {type(source).__name__}")
    if not isinstance(document, dict):
        raise PipelineError("pipeline document must be an object")
    return document


def _load_pipeline_from_text(source: Union[str, Path]) -> Dict[str, Any]:
    path = Path(source)
    text = path.read_text(encoding="utf-8") if path.is_file() else str(source)
    try:
        return json.loads(text)
    except ValueError as error:
        raise PipelineError(f"pipeline source is not JSON: {error}") from error


def _parse_stage(index: int, entry: Any, seen: set) -> PipelineStage:
    if not isinstance(entry, dict):
        raise PipelineError(f"stages[{index}] must be an object")
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        raise PipelineError(f"stages[{index}].name must be non-empty string")
    if name in seen:
        raise PipelineError(f"duplicate stage name {name!r}")
    seen.add(name)
    files = entry.get("files")
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        raise PipelineError(f"stages[{index}].files must be list[str]")
    required_status = entry.get("required_status") or ["passed"]
    if (not isinstance(required_status, list)
            or not all(isinstance(s, str) for s in required_status)):
        raise PipelineError(
            f"stages[{index}].required_status must be list[str]"
        )
    return PipelineStage(
        name=name,
        files=list(files),
        required_status=list(required_status),
        continue_on_failure=bool(entry.get("continue_on_failure", False)),
    )


FileRunner = Callable[[str], Dict[str, Any]]


def run_pipeline(
    pipeline: Pipeline,
    runner: FileRunner,
    file_resolver: Optional[Callable[[str], List[str]]] = None,
) -> List[PipelineResult]:
    """
    依宣告順序跑 pipeline。Stage 失敗時：
    - ``continue_on_failure=True`` → 收集失敗、進下一 stage
    - 否則 → 中斷後續 stage，標記為 ``skipped``。
    """
    if not isinstance(pipeline, Pipeline):
        raise PipelineError("pipeline must be a Pipeline instance")
    if not callable(runner):
        raise PipelineError("runner must be callable")
    resolver = file_resolver or (lambda pattern: [pattern])
    results: List[PipelineResult] = []
    short_circuit_cause: Optional[PipelineResult] = None
    for stage in pipeline.stages:
        if short_circuit_cause is not None:
            results.append(PipelineResult(
                stage_name=stage.name,
                status="skipped",
                error=f"previous stage {short_circuit_cause.stage_name!r} blocked",
            ))
            continue
        stage_result = _run_stage(stage, runner, resolver)
        results.append(stage_result)
        if (stage_result.status not in stage.required_status
                and not stage.continue_on_failure):
            short_circuit_cause = stage_result
    return results


def _run_stage(stage: PipelineStage, runner: FileRunner,
               resolver: Callable[[str], List[str]]) -> PipelineResult:
    try:
        files = _flatten_files(stage.files, resolver)
    except PipelineError as error:
        return PipelineResult(
            stage_name=stage.name, status="failed", error=str(error),
        )
    if not files:
        return PipelineResult(stage_name=stage.name, status="passed")
    file_outcomes: List[Dict[str, Any]] = []
    overall = "passed"
    for path in files:
        try:
            outcome = runner(path) or {}
            file_outcomes.append({"path": path, **outcome})
            if outcome.get("status") and outcome["status"] != "passed":
                overall = "failed"
        except Exception as error:  # pylint: disable=broad-except
            file_outcomes.append({"path": path, "status": "failed",
                                  "error": repr(error)})
            overall = "failed"
    return PipelineResult(
        stage_name=stage.name,
        status=overall,
        file_results=file_outcomes,
    )


def _flatten_files(patterns: Sequence[str],
                   resolver: Callable[[str], List[str]]) -> List[str]:
    files: List[str] = []
    seen: set = set()
    for pattern in patterns:
        resolved = resolver(pattern)
        if not isinstance(resolved, list):
            raise PipelineError(
                f"file_resolver returned non-list for {pattern!r}"
            )
        for path in resolved:
            text = str(path)
            if text not in seen:
                seen.add(text)
                files.append(text)
    return files


def assert_all_passed(results: Iterable[PipelineResult]) -> None:
    """Raise if any stage status is not ``passed``."""
    bad = [r for r in results if r.status != "passed"]
    if bad:
        sample = [{"stage": r.stage_name, "status": r.status} for r in bad[:5]]
        raise PipelineError(f"{len(bad)} pipeline stage(s) not passing: {sample}")
