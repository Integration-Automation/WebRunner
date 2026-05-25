"""
HAR → OpenAPI 3.x reverse-engineering.

Walks a HAR file (the kind devtools / Charles / mitmproxy spits out) and
produces a draft OpenAPI 3.1 spec. Good for legacy back-ends that never
shipped a spec.

It is intentionally lossy:

* Path parameters are inferred by collapsing numeric / UUID segments.
* Response schemas are sketched from observed JSON keys + JS types.
* Query parameters listed are union of all observed.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlparse, parse_qsl

from je_web_runner.utils.exception.exceptions import WebRunnerException


class HarToOpenapiError(WebRunnerException):
    """Raised on malformed HAR input or impossible conversion."""


_NUMERIC_RE = re.compile(r"^\d+$")
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
)


def _classify_segment(seg: str) -> Optional[str]:
    if _NUMERIC_RE.match(seg):
        return "{id}"
    if _UUID_RE.match(seg):
        return "{uuid}"
    return None


def _path_template(path: str) -> str:
    parts = path.split("/")
    out: List[str] = []
    for seg in parts:
        if not seg:
            out.append(seg)
            continue
        replacement = _classify_segment(seg)
        out.append(replacement or seg)
    return "/".join(out)


def _js_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "null"


def _schema_from_value(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {k: _schema_from_value(v) for k, v in value.items()},
        }
    if isinstance(value, list):
        if not value:
            return {"type": "array", "items": {}}
        return {"type": "array",
                "items": _schema_from_value(value[0])}
    return {"type": _js_type(value)}


def _parse_body(content: Any) -> Any:
    if not isinstance(content, str):
        return None
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        return None


def _merge_query_params(op: Dict[str, Any], query: str) -> None:
    existing = {p["name"] for p in op["parameters"]}
    for q_name, _ in parse_qsl(query):
        if q_name not in existing:
            op["parameters"].append({
                "name": q_name, "in": "query",
                "schema": {"type": "string"},
            })
            existing.add(q_name)


def _merge_response(op: Dict[str, Any], status: str, body: Any) -> None:
    if body is None:
        op["responses"].setdefault(status, {"description": "auto-generated"})
        return
    op["responses"].setdefault(status, {
        "description": "auto-generated",
        "content": {"application/json": {"schema": _schema_from_value(body)}},
    })


def _register_entry(
    paths: Dict[str, Dict[str, Any]], entry: Dict[str, Any],
) -> None:
    req = entry.get("request") or {}
    res = entry.get("response") or {}
    url = req.get("url")
    method = (req.get("method") or "GET").lower()
    if not url:
        return
    parsed = urlparse(url)
    path_template = _path_template(parsed.path or "/")
    op = paths[path_template].setdefault(method, {
        "summary": f"Auto-generated from {method.upper()} {parsed.path}",
        "parameters": [],
        "responses": {},
    })
    _merge_query_params(op, parsed.query)
    _merge_response(op, str(res.get("status") or 200),
                    _parse_body((res.get("content") or {}).get("text")))


def convert(har: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(har, Mapping):
        raise HarToOpenapiError("har must be a mapping")
    log = har.get("log")
    entries = log.get("entries") if isinstance(log, Mapping) else None
    if not isinstance(entries, list):
        raise HarToOpenapiError("har.log.entries must be a list")
    paths: Dict[str, Dict[str, Any]] = defaultdict(dict)
    for entry in entries:
        if isinstance(entry, dict):
            _register_entry(paths, entry)
    return {
        "openapi": "3.1.0",
        "info": {"title": "Reverse-engineered API", "version": "0.0.1"},
        "paths": dict(paths),
    }


def assert_spec_minimum_coverage(
    spec: Mapping[str, Any], *, min_paths: int,
) -> None:
    if min_paths < 1:
        raise HarToOpenapiError("min_paths must be >= 1")
    paths = spec.get("paths") or {}
    if not isinstance(paths, Mapping) or len(paths) < min_paths:
        raise HarToOpenapiError(
            f"spec only covers {len(paths)} paths, expected >= {min_paths}"
        )
