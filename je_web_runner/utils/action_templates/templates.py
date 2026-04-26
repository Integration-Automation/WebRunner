"""
可重用的 action 樣板：登入 / 接受 cookie / 切換語系等流程一行帶過。
Action template library. Templates are parameterised lists of WR commands;
:meth:`render_template` substitutes ``{{placeholder}}`` tokens with caller-
provided values and returns a fresh action list ready for the executor.

Built-in templates:
- ``login_basic``: ``[fill username, fill password, click submit]``.
- ``accept_cookies``: dispatches to the cookie-consent dismisser.
- ``switch_locale``: query-string locale flip.
- ``close_modal``: send Escape twice (handles double-stacked modals).
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class ActionTemplateError(WebRunnerException):
    """Raised when template lookup, registration, or render fails."""


@dataclass
class ActionTemplate:
    name: str
    actions: List[Any]
    parameters: Sequence[str] = field(default_factory=tuple)
    description: str = ""


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_]\w*)\s*\}\}")


_BUILTIN_TEMPLATES: Dict[str, ActionTemplate] = {
    "login_basic": ActionTemplate(
        name="login_basic",
        parameters=("username_locator", "password_locator", "submit_locator",
                    "username", "password"),
        description="Fill username + password fields and click the submit button.",
        actions=[
            ["WR_save_test_object", {"test_object_name": "{{username_locator}}",
                                     "object_type": "CSS_SELECTOR"}],
            ["WR_find_recorded_element", {"element_name": "{{username_locator}}"}],
            ["WR_element_input", {"input_value": "{{username}}"}],
            ["WR_save_test_object", {"test_object_name": "{{password_locator}}",
                                     "object_type": "CSS_SELECTOR"}],
            ["WR_find_recorded_element", {"element_name": "{{password_locator}}"}],
            ["WR_element_input", {"input_value": "{{password}}"}],
            ["WR_save_test_object", {"test_object_name": "{{submit_locator}}",
                                     "object_type": "CSS_SELECTOR"}],
            ["WR_find_recorded_element", {"element_name": "{{submit_locator}}"}],
            ["WR_element_click"],
        ],
    ),
    "accept_cookies": ActionTemplate(
        name="accept_cookies",
        parameters=(),
        description="Auto-dismiss common cookie / GDPR consent banners.",
        actions=[
            ["WR_dismiss_cookie_consent"],
        ],
    ),
    "switch_locale": ActionTemplate(
        name="switch_locale",
        parameters=("base_url", "locale"),
        description="Navigate to ``base_url?lang=<locale>``.",
        actions=[
            ["WR_to_url", {"url": "{{base_url}}?lang={{locale}}"}],
        ],
    ),
    "close_modal": ActionTemplate(
        name="close_modal",
        parameters=(),
        description="Send Escape twice (handles double-stacked modals).",
        actions=[
            ["WR_press_keys", {"keys": "Escape"}],
            ["WR_press_keys", {"keys": "Escape"}],
        ],
    ),
}


def available_templates() -> List[str]:
    return sorted(_BUILTIN_TEMPLATES.keys())


def get_template(name: str) -> ActionTemplate:
    if name not in _BUILTIN_TEMPLATES:
        raise ActionTemplateError(
            f"unknown template {name!r}; available: {available_templates()}"
        )
    return _BUILTIN_TEMPLATES[name]


def register_template(template: ActionTemplate) -> None:
    if not isinstance(template, ActionTemplate):
        raise ActionTemplateError("template must be an ActionTemplate instance")
    _BUILTIN_TEMPLATES[template.name] = template


def render_template(name: str, parameters: Optional[Dict[str, Any]] = None) -> List[Any]:
    """
    把 ``{{name}}`` 替換成實際值，回傳深拷貝的 action list
    Substitute every ``{{name}}`` placeholder in the template with the
    matching value from ``parameters`` and return a deep-copied action list.
    Raises :class:`ActionTemplateError` if any required parameter is missing.
    """
    template = get_template(name)
    params = parameters or {}
    missing = [p for p in template.parameters if p not in params]
    if missing:
        raise ActionTemplateError(
            f"template {name!r} missing parameters: {missing}"
        )
    return [
        _substitute(action, params, name)
        for action in copy.deepcopy(template.actions)
    ]


def _substitute(node: Any, params: Dict[str, Any], template_name: str) -> Any:
    if isinstance(node, str):
        return _substitute_text(node, params, template_name)
    if isinstance(node, list):
        return [_substitute(item, params, template_name) for item in node]
    if isinstance(node, dict):
        return {k: _substitute(v, params, template_name) for k, v in node.items()}
    return node


def _substitute_text(text: str, params: Dict[str, Any], template_name: str) -> Any:
    matches = list(_PLACEHOLDER_RE.finditer(text))
    if not matches:
        return text
    if len(matches) == 1 and matches[0].group(0) == text:
        key = matches[0].group(1)
        if key not in params:
            raise ActionTemplateError(
                f"template {template_name!r} placeholder {{{{{key}}}}} unbound"
            )
        return params[key]

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in params:
            raise ActionTemplateError(
                f"template {template_name!r} placeholder {{{{{key}}}}} unbound"
            )
        return str(params[key])

    return _PLACEHOLDER_RE.sub(_replace, text)
