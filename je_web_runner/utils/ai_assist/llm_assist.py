"""
LLM-輔助：可插拔的 LLM caller，供 self-healing 與 NL 測試生成使用。
LLM-assisted helpers. WebRunner does not ship a built-in LLM client; the
caller registers any ``Callable[[str], str]`` and these helpers route
prompts through it. Keep the boundary explicit so swapping providers
(OpenAI / Anthropic / local) is a one-line change.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class LLMAssistError(WebRunnerException):
    """Raised when no LLM callable is registered or the response is malformed."""


_llm_callable: Optional[Callable[[str], str]] = None


def set_llm_callable(callable_obj: Optional[Callable[[str], str]]) -> None:
    """登錄一個 ``Callable[[str], str]`` 用於後續所有 prompt。"""
    global _llm_callable
    _llm_callable = callable_obj


def has_llm_callable() -> bool:
    return _llm_callable is not None


def _invoke(prompt: str) -> str:
    if _llm_callable is None:
        raise LLMAssistError(
            "no LLM callable registered; call set_llm_callable(fn) first"
        )
    web_runner_logger.info("LLM prompt invoked")
    response = _llm_callable(prompt)
    if not isinstance(response, str):
        raise LLMAssistError(f"LLM callable must return str, got {type(response).__name__}")
    return response


_LOCATOR_PROMPT = (
    "You are a web testing helper. Given an HTML snippet and a description "
    "of the desired element, output ONLY a JSON object: "
    '{{"strategy": "ID|NAME|CSS_SELECTOR|XPATH|LINK_TEXT", "value": "..."}}. '
    "No prose.\n\nHTML:\n{html}\n\nElement to find: {description}\n"
)


def suggest_locator(html: str, description: str) -> Dict[str, str]:
    """
    讓 LLM 從 HTML 推斷一個合理的 locator
    Ask the registered LLM to pick a locator. Returns
    ``{"strategy": ..., "value": ...}``.
    """
    response = _invoke(_LOCATOR_PROMPT.format(html=html[:6000], description=description))
    payload = _extract_json_object(response)
    if not isinstance(payload, dict) or "strategy" not in payload or "value" not in payload:
        raise LLMAssistError(f"LLM returned unexpected payload: {response[:200]}")
    return {"strategy": str(payload["strategy"]), "value": str(payload["value"])}


_ACTION_PROMPT = (
    "You generate WebRunner action JSON arrays. Output ONLY a JSON array of "
    "actions; each action is [\"WR_*\", {{kwargs}}] or [\"WR_*\"]. No prose.\n"
    "Available command names include WR_to_url, WR_save_test_object, "
    "WR_find_recorded_element, WR_element_input, WR_element_click, "
    "WR_element_assert, WR_quit_all.\n"
    "Context: {context}\n\nUser request: {request}\n"
)


def generate_actions_from_prompt(
    request: str,
    context: Optional[str] = None,
) -> List[Any]:
    """
    把自然語言敘述轉成 WR_* action JSON 草稿
    Translate a natural-language request into an action JSON list. The LLM
    must return only a JSON array; this helper extracts and parses it.
    """
    response = _invoke(_ACTION_PROMPT.format(request=request, context=context or ""))
    parsed = _extract_json_array(response)
    if not isinstance(parsed, list):
        raise LLMAssistError(f"LLM returned non-array payload: {response[:200]}")
    return parsed


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)


def _extract_json_object(text: str) -> Any:
    match = _JSON_OBJECT_RE.search(text)
    if match is None:
        raise LLMAssistError("no JSON object found in LLM response")
    try:
        return json.loads(match.group(0))
    except ValueError as error:
        raise LLMAssistError(f"LLM JSON object did not parse: {error}") from error


def _extract_json_array(text: str) -> Any:
    match = _JSON_ARRAY_RE.search(text)
    if match is None:
        raise LLMAssistError("no JSON array found in LLM response")
    try:
        return json.loads(match.group(0))
    except ValueError as error:
        raise LLMAssistError(f"LLM JSON array did not parse: {error}") from error


# ----- self-healing locator hook ------------------------------------------

def llm_self_heal_locator(name: str, html_provider: Callable[[], str]) -> Dict[str, str]:
    """
    當既有 fallback locator 都失敗時，呼叫 LLM 提供新的選擇器
    Last-resort hook for the self-healing locator: when the registered
    fallbacks all miss, ``html_provider()`` should return the current page
    HTML and this function asks the LLM for a fresh suggestion. Returns
    a ``{strategy, value}`` dict suitable for register_fallback.
    """
    web_runner_logger.info(f"llm_self_heal_locator: {name}")
    return suggest_locator(html_provider(), name)


# ----- failure root-cause analysis -----------------------------------------

_RCA_PROMPT = (
    "You are a senior web QA engineer. Given the failure context below, "
    "produce a concise root-cause analysis with these sections (no prose "
    "outside the JSON envelope): "
    '{{"likely_cause": "...", "evidence": ["..."], "next_steps": ["..."], '
    '"confidence": 0..1}}.\n\n'
    "Test name: {test_name}\n"
    "Error: {error_repr}\n"
    "Recent console:\n{console}\n"
    "Recent network:\n{network}\n"
    "Steps that ran:\n{steps}\n"
)


def explain_failure(
    test_name: str,
    error_repr: str,
    console: Optional[List[Dict[str, Any]]] = None,
    network: Optional[List[Dict[str, Any]]] = None,
    steps: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    要求 LLM 從失敗素材中產出 RCA 草稿
    Ask the registered LLM to draft a root-cause analysis. Returns
    ``{likely_cause, evidence, next_steps, confidence}``.
    """
    prompt = _RCA_PROMPT.format(
        test_name=test_name,
        error_repr=error_repr[:1500],
        console=json.dumps(console or [], ensure_ascii=False)[:1500],
        network=json.dumps(network or [], ensure_ascii=False)[:1500],
        steps=json.dumps(steps or [], ensure_ascii=False)[:1500],
    )
    response = _invoke(prompt)
    payload = _extract_json_object(response)
    expected = {"likely_cause", "evidence", "next_steps", "confidence"}
    if not isinstance(payload, dict) or not expected.issubset(payload.keys()):
        raise LLMAssistError(f"LLM RCA payload missing keys: {response[:200]}")
    return payload
