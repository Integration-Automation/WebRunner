"""
JSON Schema 子集驗證器：對 ``type``/``properties``/``required``/``items``/``enum``
做最小可用的合約驗證，不依賴 ``jsonschema`` 套件。
Minimal JSON-schema validator covering the subset most useful for HTTP
contract testing: ``type``, ``properties``, ``required``, ``items``,
``enum``, ``additionalProperties``, ``oneOf``. Intended for response-shape
guards, not full Draft-7 conformance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ContractError(WebRunnerException):
    """Raised when validation fails."""


@dataclass
class SchemaResult:
    valid: bool
    errors: List[str] = field(default_factory=list)


_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def _validate(value: Any, schema: Dict[str, Any], path: str,
              errors: List[str]) -> None:
    if not isinstance(schema, dict):
        errors.append(f"{path}: schema must be a dict")
        return
    if "oneOf" in schema:
        candidates = schema["oneOf"]
        any_match = False
        for sub in candidates:
            sub_errors: List[str] = []
            _validate(value, sub, path, sub_errors)
            if not sub_errors:
                any_match = True
                break
        if not any_match:
            errors.append(f"{path}: did not match any oneOf candidate")
        return
    expected = schema.get("type")
    if expected is not None:
        check = _TYPE_CHECKS.get(expected)
        if check is None:
            errors.append(f"{path}: unsupported type {expected!r}")
            return
        if not check(value):
            errors.append(f"{path}: expected {expected}, got {type(value).__name__}")
            return
    enum = schema.get("enum")
    if enum is not None and value not in enum:
        errors.append(f"{path}: value {value!r} not in enum {enum!r}")
        return
    if expected == "object":
        _validate_object(value, schema, path, errors)
    elif expected == "array":
        _validate_array(value, schema, path, errors)


def _validate_object(value: Dict[str, Any], schema: Dict[str, Any],
                     path: str, errors: List[str]) -> None:
    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    for prop in required:
        if prop not in value:
            errors.append(f"{path}: missing required property {prop!r}")
    for prop, sub_schema in properties.items():
        if prop in value:
            _validate(value[prop], sub_schema, f"{path}.{prop}", errors)
    if schema.get("additionalProperties") is False:
        extras = set(value.keys()) - set(properties.keys())
        if extras:
            errors.append(f"{path}: unexpected properties {sorted(extras)}")


def _validate_array(value: List[Any], schema: Dict[str, Any],
                    path: str, errors: List[str]) -> None:
    items_schema = schema.get("items")
    if items_schema is None:
        return
    for index, item in enumerate(value):
        _validate(item, items_schema, f"{path}[{index}]", errors)


def validate_response(response_body: Any, schema: Dict[str, Any]) -> SchemaResult:
    """Validate ``response_body`` against ``schema``."""
    errors: List[str] = []
    _validate(response_body, schema, "$", errors)
    return SchemaResult(valid=not errors, errors=errors)


def validate_against_openapi(
    response_body: Any,
    openapi_doc: Dict[str, Any],
    path: str,
    method: str,
    status: int,
) -> SchemaResult:
    """
    從 OpenAPI 3 文件抓出對應 schema 後驗證
    Look up ``paths[path][method].responses[status].content."application/json".schema``
    in an OpenAPI 3 document, then validate the response body.
    """
    paths = openapi_doc.get("paths", {})
    operation = paths.get(path, {}).get(method.lower())
    if operation is None:
        raise ContractError(f"OpenAPI doc has no {method.upper()} {path!r}")
    response = operation.get("responses", {}).get(str(status))
    if response is None:
        raise ContractError(
            f"OpenAPI doc has no {status} response for {method.upper()} {path!r}"
        )
    schema = (
        response.get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    if schema is None:
        raise ContractError(
            f"OpenAPI {method.upper()} {path!r} {status}: no application/json schema"
        )
    return validate_response(response_body, _resolve_refs(schema, openapi_doc))


def _resolve_refs(schema: Any, doc: Dict[str, Any], depth: int = 0) -> Any:
    """Inline ``$ref`` definitions from ``components/schemas`` (max depth 8)."""
    if depth > 8 or not isinstance(schema, dict):
        return schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/components/schemas/"):
            return schema
        name = ref.split("/")[-1]
        target = doc.get("components", {}).get("schemas", {}).get(name)
        if target is None:
            return schema
        return _resolve_refs(target, doc, depth + 1)
    resolved: Dict[str, Any] = {}
    for key, value in schema.items():
        if isinstance(value, dict):
            resolved[key] = _resolve_refs(value, doc, depth + 1)
        elif isinstance(value, list):
            resolved[key] = [_resolve_refs(item, doc, depth + 1) for item in value]
        else:
            resolved[key] = value
    return resolved


def assert_valid(response_body: Any, schema: Dict[str, Any]) -> None:
    """Convenience: raise on validation failure."""
    result = validate_response(response_body, schema)
    if not result.valid:
        raise ContractError(f"contract violations: {result.errors[:5]}")
