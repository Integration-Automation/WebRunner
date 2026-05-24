"""
OpenAPI / Swagger → WebRunner action JSON generator。
讀 OpenAPI 3.x 或 Swagger 2.0 spec,對每個 endpoint 產出 happy-path
+ 4xx 邊界的 ``WR_http_*`` action JSON。

Decisions:

* No external `openapi-spec-validator` dependency — we tolerate
  partially-valid specs the way real-world swagger files are.
* Examples come from (in priority): explicit ``example``/``examples``
  in the schema, then ``default``, then a type-driven faker
  (``"string"`` → ``"sample"``, ``"integer"`` → ``1``…). Keeps output
  deterministic.
* Auth: if the spec declares Bearer / API-key, we drop a placeholder
  header so the generated file is runnable after the user injects a
  real token via env-var expansion (``${ENV_VAR}``).

Output is plain ``WR_http_*`` action lists — runnable by the existing
executor without any extra glue.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class OpenAPIGeneratorError(WebRunnerException):
    """Raised when the spec is unreadable or required fields are missing."""


SUPPORTED_METHODS: Tuple[str, ...] = (
    "get", "post", "put", "patch", "delete", "head", "options",
)


@dataclass
class GeneratedTest:
    """One generated test scenario."""

    name: str
    method: str
    path: str
    expected_status: int
    actions: List[Any]
    scenario: str  # "happy" | "missing_body" | "bad_path_param" | etc.

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "method": self.method,
            "path": self.path,
            "expected_status": self.expected_status,
            "actions": self.actions,
            "scenario": self.scenario,
        }


@dataclass
class GenerationResult:
    """Aggregate result for one spec."""

    spec_title: str
    base_url: str
    tests: List[GeneratedTest] = field(default_factory=list)
    skipped: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spec_title": self.spec_title,
            "base_url": self.base_url,
            "tests": [t.to_dict() for t in self.tests],
            "skipped": list(self.skipped),
        }


# ---------- spec loading ------------------------------------------------

def load_spec(spec_path: Union[str, Path]) -> Dict[str, Any]:
    """
    讀 JSON 或 YAML 格式的 OpenAPI spec。
    YAML support is soft-dependency on ``PyYAML``; JSON specs work without.
    """
    path = Path(spec_path)
    if not path.is_file():
        raise OpenAPIGeneratorError(f"spec file not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except ValueError:
        pass
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as error:
        raise OpenAPIGeneratorError(
            f"YAML spec but PyYAML not installed: pip install pyyaml ({path})"
        ) from error
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as error:  # type: ignore[attr-defined]
        raise OpenAPIGeneratorError(f"cannot parse YAML {path}: {error}") from error
    if not isinstance(loaded, dict):
        raise OpenAPIGeneratorError(f"top-level YAML must be a mapping: {path}")
    return loaded


# ---------- $ref resolution --------------------------------------------

_REF_RE = re.compile(r"^#/(.+)$")


def _resolve_ref(spec: Dict[str, Any], ref: str) -> Any:
    match = _REF_RE.match(ref or "")
    if not match:
        return None
    parts = match.group(1).split("/")
    node: Any = spec
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _maybe_resolve(spec: Dict[str, Any], schema: Any, *, depth: int = 0) -> Any:
    if depth > 6 or not isinstance(schema, dict):
        return schema
    if "$ref" in schema:
        resolved = _resolve_ref(spec, schema["$ref"])
        if resolved is None:
            return {}
        return _maybe_resolve(spec, resolved, depth=depth + 1)
    return schema


# ---------- example synthesis ------------------------------------------

_TYPE_DEFAULTS: Dict[str, Any] = {
    "string": "sample",
    "integer": 1,
    "number": 1.0,
    "boolean": True,
    "array": [],
    "object": {},
}


def synthesize_example(
    spec: Dict[str, Any],
    schema: Any,
    *,
    depth: int = 0,
) -> Any:
    """
    從 schema 推一個範例值,依序試 example → default → type 預設。
    Deterministic so repeated runs produce the same output. Recursion
    depth is bounded to keep cyclic refs safe.
    """
    if depth > 5:
        return None
    schema = _maybe_resolve(spec, schema, depth=depth)
    if not isinstance(schema, dict):
        return None
    if "example" in schema:
        return copy.deepcopy(schema["example"])
    if "examples" in schema:
        examples = schema["examples"]
        if isinstance(examples, dict):
            first = next(iter(examples.values()), None)
            if isinstance(first, dict) and "value" in first:
                return copy.deepcopy(first["value"])
            if first is not None:
                return copy.deepcopy(first)
        if isinstance(examples, list) and examples:
            return copy.deepcopy(examples[0])
    if "default" in schema:
        return copy.deepcopy(schema["default"])
    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        out: Dict[str, Any] = {}
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        for key, prop in properties.items():
            if required and key not in required:
                continue
            out[key] = synthesize_example(spec, prop, depth=depth + 1)
        return out
    if schema_type == "array":
        items = schema.get("items")
        if items:
            return [synthesize_example(spec, items, depth=depth + 1)]
        return []
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        return schema["enum"][0]
    if isinstance(schema_type, str) and schema_type in _TYPE_DEFAULTS:
        return copy.deepcopy(_TYPE_DEFAULTS[schema_type])
    return None


# ---------- url assembly ------------------------------------------------

def _base_url(spec: Dict[str, Any]) -> str:
    """Honour OpenAPI 3 ``servers`` first, then Swagger 2 ``host`` + ``basePath``."""
    servers = spec.get("servers")
    if isinstance(servers, list) and servers:
        first = servers[0]
        if isinstance(first, dict) and "url" in first:
            return str(first["url"]).rstrip("/")
    host = spec.get("host")
    if isinstance(host, str) and host:
        scheme = "https"
        schemes = spec.get("schemes")
        if isinstance(schemes, list) and schemes:
            scheme = str(schemes[0])
        base = f"{scheme}://{host}"
        base_path = spec.get("basePath") or ""
        if base_path and not base_path.startswith("/"):
            base_path = "/" + base_path
        return (base + base_path).rstrip("/")
    return ""


_PATH_PARAM_RE = re.compile(r"\{([^{}]+)\}")


def _expand_path(
    template: str,
    parameters: List[Dict[str, Any]],
    spec: Dict[str, Any],
    *,
    invalid_param: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Returns ``(expanded_path, query_params)``."""
    resolved = template
    query: Dict[str, Any] = {}
    for raw_param in parameters:
        param = _maybe_resolve(spec, raw_param)
        if not isinstance(param, dict):
            continue
        name = param.get("name")
        if not isinstance(name, str):
            continue
        location = param.get("in")
        if location == "path":
            example = synthesize_example(spec, param.get("schema") or param) or "1"
            if invalid_param and invalid_param == name:
                example = ""  # forces /foo// — server returns 404 or 400
            resolved = resolved.replace(
                "{" + name + "}", str(example),
            )
        elif location == "query":
            example = synthesize_example(spec, param.get("schema") or param)
            if example is not None:
                query[name] = example
    return resolved, query


def _action_command(method: str) -> str:
    return f"WR_http_{method.lower()}"


# ---------- auth heuristics --------------------------------------------

def _auth_headers(spec: Dict[str, Any]) -> Dict[str, str]:
    """
    粗略偵測 Bearer / API-key,塞 ``${TOKEN}`` placeholder 讓 env_loader 補。
    """
    components = spec.get("components") or {}
    security_schemes = components.get("securitySchemes") or spec.get("securityDefinitions") or {}
    headers: Dict[str, str] = {}
    if not isinstance(security_schemes, dict):
        return headers
    for scheme in security_schemes.values():
        if not isinstance(scheme, dict):
            continue
        kind = (scheme.get("type") or "").lower()
        if kind in {"http", "bearer"} and (scheme.get("scheme") or "").lower() == "bearer":
            headers["Authorization"] = "Bearer ${API_TOKEN}"
        elif kind in {"apikey", "api_key"} and scheme.get("in") == "header":
            header_name = str(scheme.get("name") or "X-API-Key")
            headers[header_name] = "${API_TOKEN}"
    return headers


# ---------- per-endpoint generation ------------------------------------

def _build_action(
    method: str,
    path: str,
    base_url: str,
    *,
    body: Any = None,
    query: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
) -> List[Any]:
    kwargs: Dict[str, Any] = {"url": f"{base_url}{path}", "timeout": timeout}
    if query:
        kwargs["params"] = query
    if headers:
        kwargs["headers"] = headers
    if body is not None and method.lower() in {"post", "put", "patch", "delete"}:
        kwargs["json_body"] = body
    return [_action_command(method), kwargs]


def _request_body_example(spec: Dict[str, Any], operation: Dict[str, Any]) -> Any:
    body = operation.get("requestBody")
    if isinstance(body, dict):
        body = _maybe_resolve(spec, body)
        content = body.get("content") if isinstance(body, dict) else None
        if isinstance(content, dict):
            json_payload = content.get("application/json") or next(iter(content.values()), None)
            if isinstance(json_payload, dict):
                schema = json_payload.get("schema")
                if schema is not None:
                    return synthesize_example(spec, schema)
                if "example" in json_payload:
                    return copy.deepcopy(json_payload["example"])
    # swagger 2 — `parameters` with `in: body`
    parameters = operation.get("parameters") or []
    if isinstance(parameters, list):
        for raw in parameters:
            param = _maybe_resolve(spec, raw)
            if isinstance(param, dict) and param.get("in") == "body":
                schema = param.get("schema") or param
                return synthesize_example(spec, schema)
    return None


def _success_status(operation: Dict[str, Any]) -> int:
    responses = operation.get("responses") or {}
    if not isinstance(responses, dict):
        return 200
    for code in responses:
        if isinstance(code, str) and code.startswith("2"):
            try:
                return int(code)
            except ValueError:
                continue
    return 200


def _operation_name(method: str, path: str, operation: Dict[str, Any]) -> str:
    op_id = operation.get("operationId")
    if isinstance(op_id, str) and op_id:
        return op_id
    sanitised = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_") or "root"
    return f"{method.lower()}_{sanitised}"


def _build_happy_test(
    spec: Dict[str, Any],
    base_url: str,
    method: str,
    path: str,
    operation: Dict[str, Any],
    extra_headers: Dict[str, str],
) -> GeneratedTest:
    parameters = list(operation.get("parameters") or [])
    parameters.extend(operation.get("parameters", []) if False else [])
    expanded_path, query = _expand_path(path, parameters, spec)
    body = _request_body_example(spec, operation)
    status = _success_status(operation)
    name = _operation_name(method, path, operation)
    return GeneratedTest(
        name=f"{name}__happy",
        method=method.upper(),
        path=expanded_path,
        expected_status=status,
        scenario="happy",
        actions=[
            _build_action(
                method, expanded_path, base_url,
                body=body, query=query or None,
                headers=extra_headers or None,
            ),
            ["WR_http_assert_status", {"expected": status}],
        ],
    )


def _build_missing_body_test(
    spec: Dict[str, Any],
    base_url: str,
    method: str,
    path: str,
    operation: Dict[str, Any],
    extra_headers: Dict[str, str],
) -> Optional[GeneratedTest]:
    if method.lower() not in {"post", "put", "patch"}:
        return None
    if not operation.get("requestBody") and not any(
        (_maybe_resolve(spec, p) or {}).get("in") == "body"
        for p in (operation.get("parameters") or [])
    ):
        return None
    parameters = list(operation.get("parameters") or [])
    expanded_path, query = _expand_path(path, parameters, spec)
    name = _operation_name(method, path, operation)
    return GeneratedTest(
        name=f"{name}__missing_body",
        method=method.upper(),
        path=expanded_path,
        expected_status=400,
        scenario="missing_body",
        actions=[
            _build_action(
                method, expanded_path, base_url,
                body=None, query=query or None,
                headers=extra_headers or None,
            ),
            ["WR_http_assert_status", {"expected": 400}],
        ],
    )


def _build_bad_path_param_test(
    spec: Dict[str, Any],
    base_url: str,
    method: str,
    path: str,
    operation: Dict[str, Any],
    extra_headers: Dict[str, str],
) -> Optional[GeneratedTest]:
    path_params = _PATH_PARAM_RE.findall(path)
    if not path_params:
        return None
    bad_param = path_params[0]
    parameters = list(operation.get("parameters") or [])
    expanded_path, query = _expand_path(path, parameters, spec, invalid_param=bad_param)
    body = _request_body_example(spec, operation)
    name = _operation_name(method, path, operation)
    return GeneratedTest(
        name=f"{name}__bad_path_param",
        method=method.upper(),
        path=expanded_path,
        expected_status=404,
        scenario="bad_path_param",
        actions=[
            _build_action(
                method, expanded_path, base_url,
                body=body, query=query or None,
                headers=extra_headers or None,
            ),
            ["WR_http_assert_status", {"expected": 404}],
        ],
    )


# ---------- public entry points ----------------------------------------

def generate_tests_from_spec(
    spec: Dict[str, Any],
    *,
    include_negative: bool = True,
    method_filter: Optional[Iterable[str]] = None,
    path_prefix_filter: Optional[str] = None,
) -> GenerationResult:
    """
    從已 load 的 spec 直接產出 GenerationResult。
    ``method_filter`` (e.g. ``{"get", "post"}``) and ``path_prefix_filter``
    let callers narrow the surface during big-spec exploration.
    """
    if not isinstance(spec, dict):
        raise OpenAPIGeneratorError("spec must be a dict")
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise OpenAPIGeneratorError("spec missing 'paths' object")
    base_url = _base_url(spec)
    title = ((spec.get("info") or {}).get("title")) if isinstance(spec.get("info"), dict) else ""
    extra_headers = _auth_headers(spec)
    methods_lower = (
        {m.lower() for m in method_filter} if method_filter else set(SUPPORTED_METHODS)
    )
    tests: List[GeneratedTest] = []
    skipped: List[Dict[str, str]] = []
    for path, operations in paths.items():
        if not isinstance(path, str) or not isinstance(operations, dict):
            continue
        if path_prefix_filter and not path.startswith(path_prefix_filter):
            continue
        for method, operation in operations.items():
            if method.lower() not in SUPPORTED_METHODS:
                continue
            if method.lower() not in methods_lower:
                continue
            if not isinstance(operation, dict):
                skipped.append({"path": path, "method": method, "reason": "operation not a dict"})
                continue
            tests.append(_build_happy_test(spec, base_url, method, path, operation, extra_headers))
            if include_negative:
                missing = _build_missing_body_test(
                    spec, base_url, method, path, operation, extra_headers,
                )
                if missing:
                    tests.append(missing)
                bad_path = _build_bad_path_param_test(
                    spec, base_url, method, path, operation, extra_headers,
                )
                if bad_path:
                    tests.append(bad_path)
    web_runner_logger.info(
        f"generate_tests_from_spec: title={title!r} produced={len(tests)} "
        f"skipped={len(skipped)}"
    )
    return GenerationResult(
        spec_title=str(title or ""),
        base_url=base_url,
        tests=tests,
        skipped=skipped,
    )


def generate_tests_from_file(
    spec_path: Union[str, Path],
    *,
    include_negative: bool = True,
    method_filter: Optional[Iterable[str]] = None,
    path_prefix_filter: Optional[str] = None,
) -> GenerationResult:
    """Convenience: load + generate in one shot."""
    spec = load_spec(spec_path)
    return generate_tests_from_spec(
        spec,
        include_negative=include_negative,
        method_filter=method_filter,
        path_prefix_filter=path_prefix_filter,
    )


def write_tests_to_dir(
    result: GenerationResult,
    output_dir: Union[str, Path],
) -> List[Path]:
    """One JSON file per generated test (slug-named, sorted by name)."""
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for test in result.tests:
        slug = re.sub(r"[^A-Za-z0-9_-]+", "_", test.name).strip("_")
        path = target / f"{slug}.json"
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(test.actions, fp, ensure_ascii=False, indent=2)
        written.append(path)
    web_runner_logger.info(f"write_tests_to_dir: wrote {len(written)} files to {target}")
    return written
