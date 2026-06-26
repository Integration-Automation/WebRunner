"""
Live-API vs OpenAPI spec drift detector.

Given the project's checked-in OpenAPI 3.x JSON and a list of
``ApiObservation`` records collected from actual production / staging
traffic, detect:

* Endpoint hit in traffic but NOT in spec (undocumented endpoint).
* Endpoint in spec but never hit in N days (zombie endpoint).
* Method on documented path that's used but not declared.
* Status code returned that isn't enumerated in the spec.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class OpenapiDriftError(WebRunnerException):
    """Raised on malformed input or drift assertion failure."""


@dataclass
class ApiObservation:
    method: str
    path: str
    status_code: int
    count: int = 1


@dataclass
class DriftReport:
    undocumented: list[str] = field(default_factory=list)
    zombie: list[str] = field(default_factory=list)
    undocumented_methods: list[str] = field(default_factory=list)
    undocumented_statuses: list[str] = field(default_factory=list)


def _collect_spec(spec: Mapping[str, Any]) -> dict[str, dict[str, set[str]]]:
    if not isinstance(spec, Mapping):
        raise OpenapiDriftError("spec must be a mapping")
    paths = spec.get("paths") or {}
    if not isinstance(paths, Mapping):
        raise OpenapiDriftError("spec.paths must be a mapping")
    out: dict[str, dict[str, set[str]]] = {}
    for path, methods in paths.items():
        if not isinstance(methods, Mapping):
            continue
        method_map: dict[str, set[str]] = {}
        for method, op in methods.items():
            method = method.upper()
            if method not in ("GET", "POST", "PUT", "PATCH",
                              "DELETE", "HEAD", "OPTIONS"):
                continue
            if not isinstance(op, Mapping):
                continue
            responses = op.get("responses") or {}
            method_map[method] = {str(code) for code in responses}
        out[path] = method_map
    return out


def _normalize_path(path: str, spec_paths: Iterable[str]) -> str:
    """Resolve concrete observation paths to their spec template, e.g.
    /users/42 → /users/{id}."""
    parts = path.split("/")
    for spec_path in spec_paths:
        spec_parts = spec_path.split("/")
        if len(spec_parts) != len(parts):
            continue
        match = True
        for s, p in zip(spec_parts, parts, strict=False):
            if s == p:
                continue
            if s.startswith("{") and s.endswith("}"):
                continue
            match = False
            break
        if match:
            return spec_path
    return path


def _classify_observation(
    obs: ApiObservation, spec_map: dict[str, dict[str, set[str]]],
    report: DriftReport, seen_methods: dict[str, set[str]],
) -> str | None:
    """Record drift for ``obs``; return the matched spec path if any."""
    if not isinstance(obs, ApiObservation):
        raise OpenapiDriftError("observation must be ApiObservation")
    path = _normalize_path(obs.path, spec_map.keys())
    method = obs.method.upper()
    if path not in spec_map:
        report.undocumented.append(f"{method} {obs.path}")
        return None
    if method not in spec_map[path]:
        report.undocumented_methods.append(f"{method} {path}")
        return path
    seen_methods[path].add(method)
    statuses = spec_map[path][method]
    if str(obs.status_code) not in statuses and "default" not in statuses:
        report.undocumented_statuses.append(
            f"{method} {path} → {obs.status_code}"
        )
    return path


def _collect_zombies(
    spec_map: dict[str, dict[str, set[str]]],
    seen_paths: set[str], seen_methods: dict[str, set[str]],
) -> list[str]:
    out: list[str] = []
    for spec_path, methods in spec_map.items():
        for method in methods:
            if (spec_path not in seen_paths
                    or method not in seen_methods.get(spec_path, set())):
                out.append(f"{method} {spec_path}")
    return out


def diff(
    spec: Mapping[str, Any], observations: Sequence[ApiObservation],
) -> DriftReport:
    spec_map = _collect_spec(spec)
    report = DriftReport()
    seen_paths: set[str] = set()
    seen_methods: dict[str, set[str]] = defaultdict(set)
    for obs in observations:
        matched = _classify_observation(obs, spec_map, report, seen_methods)
        if matched is not None:
            seen_paths.add(matched)
    report.zombie = _collect_zombies(spec_map, seen_paths, seen_methods)
    return report


def assert_no_undocumented(report: DriftReport) -> None:
    if report.undocumented or report.undocumented_methods:
        raise OpenapiDriftError(
            f"undocumented endpoints: paths={report.undocumented}, "
            f"methods={report.undocumented_methods}"
        )


def assert_no_zombies(report: DriftReport, *, max_zombies: int = 0) -> None:
    if max_zombies < 0:
        raise OpenapiDriftError("max_zombies must be >= 0")
    if len(report.zombie) > max_zombies:
        raise OpenapiDriftError(
            f"{len(report.zombie)} zombie endpoint(s): {report.zombie}"
        )
