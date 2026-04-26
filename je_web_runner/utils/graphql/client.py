"""
GraphQL HTTP client：發送 query/mutation、解析錯誤、簡化欄位斷言。
GraphQL helper around :func:`urllib.request`. Sends a query/mutation,
inspects the ``data`` / ``errors`` envelope, and offers a path-style field
extractor for tests.

The client is intentionally dependency-free; the ``urlopen`` call is
guarded by the same scheme allow-list as the rest of WebRunner.
"""
from __future__ import annotations

import json
import ssl
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class GraphQLError(WebRunnerException):
    """Raised when the GraphQL response contains errors or transport fails."""


_INTROSPECTION_QUERY = """
{
  __schema {
    types {
      name
      kind
      fields { name type { name kind ofType { name kind } } }
    }
  }
}
"""


@dataclass
class GraphQLClient:
    endpoint: str
    headers: Optional[Dict[str, str]] = None
    timeout: float = 10.0

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, str) or not (
            self.endpoint.startswith("http://") or self.endpoint.startswith("https://")  # NOSONAR — scheme allow-list
        ):
            raise GraphQLError(f"endpoint must be http(s): {self.endpoint!r}")
        if self.headers is None:
            self.headers = {}

    def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        request = self._build_request(query, variables, operation_name)
        payload = self._send(request)
        web_runner_logger.info(
            f"graphql {operation_name or query.split()[0]} keys={list(payload.keys())}"
        )
        if isinstance(payload.get("errors"), list) and payload["errors"]:
            raise GraphQLError(f"GraphQL errors: {payload['errors'][:3]}")
        return payload

    def _build_request(
        self,
        query: str,
        variables: Optional[Dict[str, Any]],
        operation_name: Optional[str],
    ) -> urllib.request.Request:
        body = json.dumps(
            {"query": query, "variables": variables or {}, "operationName": operation_name},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(self.endpoint, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")
        for name, value in (self.headers or {}).items():
            request.add_header(name, value)
        return request

    def _send(self, request: urllib.request.Request) -> Dict[str, Any]:
        ssl_context = ssl.create_default_context()  # NOSONAR — Py3.10+ default enforces TLS 1.2+
        try:
            with urllib.request.urlopen(  # nosec B310 — scheme already validated
                request, timeout=self.timeout, context=ssl_context,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, ValueError) as error:
            raise GraphQLError(f"GraphQL transport failed: {error!r}") from error

    def introspect(self) -> Dict[str, Any]:
        return self.execute(_INTROSPECTION_QUERY)


def extract_field(payload: Dict[str, Any], path: str) -> Any:
    """
    用 ``a.b.c[0].d`` 形式的路徑從 GraphQL 回應中取值
    Pluck a value out of ``payload['data']`` using a dotted path with optional
    ``[index]`` accessors.
    """
    if not isinstance(payload, dict) or "data" not in payload:
        raise GraphQLError("payload missing data envelope")
    cursor: Any = payload["data"]
    for raw_part in path.split("."):
        if not raw_part:
            raise GraphQLError(f"empty path segment in {path!r}")
        name, index = _split_part(raw_part)
        if name:
            cursor = _get_field(cursor, name, path)
        if index is not None:
            cursor = _get_index(cursor, index, path)
    return cursor


def _split_part(raw_part: str) -> tuple:
    """Return ``(name, index)`` for a path segment like ``users[0]``."""
    if "[" in raw_part and raw_part.endswith("]"):
        name, _, rest = raw_part.partition("[")
        try:
            return name, int(rest[:-1])
        except ValueError as error:
            raise GraphQLError(f"bad index in {raw_part!r}") from error
    return raw_part, None


def _get_field(cursor: Any, name: str, path: str) -> Any:
    if not isinstance(cursor, dict) or name not in cursor:
        raise GraphQLError(f"field {name!r} missing at {path!r}")
    return cursor[name]


def _get_index(cursor: Any, index: int, path: str) -> Any:
    if not isinstance(cursor, list) or index >= len(cursor):
        raise GraphQLError(f"index {index} out of range at {path!r}")
    return cursor[index]


def introspect_types(payload: Dict[str, Any]) -> List[str]:
    """Return the list of type names from an introspection payload."""
    schema = payload.get("data", {}).get("__schema", {})
    return [t.get("name") for t in schema.get("types", []) if t.get("name")]
