"""
Old client × new server backward compatibility verifier.

Catches the classic SaaS regressions:

* New release renamed a JSON field (``user_name`` → ``username``) and
  every mobile client < N is now broken.
* New release changed a field type (``int`` → ``str``) and old client
  crashes on JSON parse.
* New release deleted a field old client depended on.
* New release added a *required* field that old client never sends.

Driven by an ``ApiContract`` baseline (the contract the old client
expects) and a list of live responses / requests recorded from the new
server.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ApiVersionCompatError(WebRunnerException):
    """Raised on incompatibility."""


@dataclass
class FieldSpec:
    name: str
    type: str       # "string" | "integer" | "number" | "boolean" | "object" | "array"
    required: bool = True


@dataclass
class ApiContract:
    """The shape the old client relies on for one endpoint."""

    endpoint: str
    response_fields: List[FieldSpec] = field(default_factory=list)
    request_fields: List[FieldSpec] = field(default_factory=list)


_TYPE_MAP = {
    "string": str, "integer": int, "number": (int, float),
    "boolean": bool, "object": dict, "array": list,
}


def _check_response(
    contract: ApiContract, response: Mapping[str, Any],
) -> List[str]:
    problems: List[str] = []
    for spec in contract.response_fields:
        if spec.name not in response:
            if spec.required:
                problems.append(
                    f"response missing required field {spec.name!r}"
                )
            continue
        expected_type = _TYPE_MAP.get(spec.type)
        if expected_type and not isinstance(response[spec.name], expected_type):
            problems.append(
                f"response field {spec.name!r}: "
                f"old client expects {spec.type}, "
                f"got {type(response[spec.name]).__name__}"
            )
    return problems


def _check_request(
    contract: ApiContract, request: Mapping[str, Any],
) -> List[str]:
    problems: List[str] = []
    required_old = {f.name for f in contract.request_fields if f.required}
    for missing in required_old - set(request.keys()):
        problems.append(
            f"old client never sends required field {missing!r} → "
            "server must accept its absence"
        )
    return problems


def assert_response_compatible(
    contract: ApiContract, response: Mapping[str, Any],
) -> None:
    if not isinstance(contract, ApiContract):
        raise ApiVersionCompatError("contract must be ApiContract")
    if not isinstance(response, Mapping):
        raise ApiVersionCompatError("response must be a mapping")
    problems = _check_response(contract, response)
    if problems:
        raise ApiVersionCompatError(
            f"response breaks old-client contract for "
            f"{contract.endpoint!r}: {problems}"
        )


def assert_request_compatible(
    contract: ApiContract, server_required_fields: Iterable[str],
) -> None:
    if not isinstance(contract, ApiContract):
        raise ApiVersionCompatError("contract must be ApiContract")
    server_required = set(server_required_fields)
    old_known = {f.name for f in contract.request_fields}
    surprise = server_required - old_known
    if surprise:
        raise ApiVersionCompatError(
            f"new server requires fields the old client doesn't send: "
            f"{sorted(surprise)}"
        )


@dataclass
class CompatMatrixRow:
    client_version: str
    server_version: str
    passed: bool
    notes: str = ""


def matrix_summary(rows: Iterable[CompatMatrixRow]) -> List[Dict[str, Any]]:
    return [{"client": r.client_version, "server": r.server_version,
             "passed": r.passed, "notes": r.notes} for r in rows]


def assert_full_matrix_passes(rows: Iterable[CompatMatrixRow]) -> None:
    fails = [r for r in rows if not r.passed]
    if fails:
        raise ApiVersionCompatError(
            f"{len(fails)} client/server combo(s) incompatible: "
            f"{[(r.client_version, r.server_version) for r in fails]}"
        )
