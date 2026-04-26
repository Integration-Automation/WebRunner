"""
Form 自動填值：依 label / placeholder / name / type 推欄位用途，從 fixture dict 一鍵填單。
Heuristic form auto-fill. Take a list of *form field descriptors* (a thin
projection of an HTML ``<input>`` / ``<select>`` / ``<textarea>``) and a
fixture dict and return:

- :class:`FieldMatch` — every matched field with its mapped fixture key.
- :func:`plan_fill_actions` — a ``WR_*`` action JSON list ready for the
  executor.

The matcher prefers, in order: explicit ``name``/``id``, ``data-testid``,
``placeholder``, then ``label`` text. Conservative aliases (``email`` ↔
``e-mail``, ``phone`` ↔ ``mobile``/``tel``) keep false positives low.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FormAutoFillError(WebRunnerException):
    """Raised when input shape is invalid."""


@dataclass
class FieldMatch:
    field: Dict[str, Any]
    fixture_key: str
    value: Any
    confidence: float
    reason: str


_NORMALISE_RE = re.compile(r"[^a-z0-9]+")


_ALIAS_BUCKETS: Dict[str, List[str]] = {
    "email": ["email", "e-mail", "emailaddress", "useremail"],
    "username": ["username", "user", "userid", "login", "account"],
    "password": ["password", "pass", "passwd", "pwd"],
    "first_name": ["firstname", "givenname", "fname"],
    "last_name": ["lastname", "familyname", "surname", "lname"],
    "full_name": ["fullname", "name", "displayname"],
    "phone": ["phone", "phonenumber", "mobile", "cell", "tel"],
    "address": ["address", "street", "addr"],
    "city": ["city", "town"],
    "country": ["country", "region"],
    "zip": ["zip", "zipcode", "postal", "postalcode"],
    "credit_card": ["cardnumber", "creditcard", "card"],
    "cvv": ["cvv", "cvc", "securitycode"],
    "search": ["search", "q", "query", "keyword"],
}


_CANONICAL_BY_TOKEN: Dict[str, str] = {}
for canonical, aliases in _ALIAS_BUCKETS.items():
    for alias in aliases:
        _CANONICAL_BY_TOKEN[alias] = canonical


def _normalise(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return _NORMALISE_RE.sub("", text.lower())


def classify_field(field: Dict[str, Any]) -> Optional[str]:
    """
    依 ``data-testid`` > ``id`` > ``name`` > ``placeholder`` > ``label`` > ``type``
    Pick the first matching alias group; return the canonical key or None.
    """
    if not isinstance(field, dict):
        return None
    field_type = str(field.get("type") or "").lower()
    if field_type == "password":
        return "password"
    if field_type == "email":
        return "email"
    if field_type in {"tel", "phone"}:
        return "phone"
    if field_type == "search":
        return "search"
    candidates = [
        field.get("data-testid"),
        field.get("id"),
        field.get("name"),
        field.get("placeholder"),
        field.get("label"),
        field.get("aria-label"),
    ]
    for candidate in candidates:
        token = _normalise(candidate)
        if not token:
            continue
        for alias, canonical in _CANONICAL_BY_TOKEN.items():
            if alias in token:
                return canonical
    return None


def match_fields(
    fields: Iterable[Dict[str, Any]],
    fixture: Dict[str, Any],
) -> List[FieldMatch]:
    """Return a :class:`FieldMatch` for every field that maps to a fixture key."""
    if not isinstance(fixture, dict):
        raise FormAutoFillError("fixture must be a dict")
    matches: List[FieldMatch] = []
    for field in fields:
        canonical = classify_field(field)
        if canonical is None:
            continue
        fixture_key, value, reason, confidence = _pick_fixture_value(
            field=field, canonical=canonical, fixture=fixture
        )
        if fixture_key is None:
            continue
        matches.append(FieldMatch(
            field=field,
            fixture_key=fixture_key,
            value=value,
            confidence=confidence,
            reason=reason,
        ))
    return matches


def _pick_fixture_value(field: Dict[str, Any], canonical: str,
                        fixture: Dict[str, Any]):
    raw_id = str(field.get("id") or field.get("name") or "").lower()
    if raw_id and raw_id in fixture:
        return raw_id, fixture[raw_id], "exact id/name match", 1.0
    if canonical in fixture:
        return canonical, fixture[canonical], f"canonical {canonical}", 0.9
    aliases = _ALIAS_BUCKETS.get(canonical, [])
    for alias in aliases:
        if alias in fixture:
            return alias, fixture[alias], f"alias {alias}", 0.7
    return None, None, "", 0.0


def plan_fill_actions(
    fields: Iterable[Dict[str, Any]],
    fixture: Dict[str, Any],
    submit_locator: Optional[Dict[str, str]] = None,
) -> List[List[Any]]:
    """
    把比對結果展開成 ``WR_save_test_object`` + ``WR_element_input`` 序列
    Convert matches into an executable action list. ``submit_locator``
    optional ``{strategy, value}`` adds a final click.
    """
    matches = match_fields(fields, fixture)
    actions: List[List[Any]] = []
    for match in matches:
        strategy, value = _locator_for(match.field)
        if strategy is None:
            continue
        actions.append(["WR_save_test_object", {
            "test_object_name": value,
            "object_type": strategy,
        }])
        actions.append(["WR_find_recorded_element", {"element_name": value}])
        actions.append(["WR_element_input", {"input_value": match.value}])
    if submit_locator:
        actions.append(["WR_save_test_object", {
            "test_object_name": submit_locator.get("value", ""),
            "object_type": submit_locator.get("strategy", "CSS_SELECTOR"),
        }])
        actions.append(["WR_find_recorded_element", {
            "element_name": submit_locator.get("value", "")
        }])
        actions.append(["WR_element_click"])
    return actions


def _locator_for(field: Dict[str, Any]):
    if field.get("id"):
        return "ID", field["id"]
    if field.get("data-testid"):
        return "CSS_SELECTOR", f"[data-testid=\"{field['data-testid']}\"]"
    if field.get("name"):
        return "NAME", field["name"]
    return None, None
