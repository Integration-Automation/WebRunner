"""
Page Object Model 骨架產生器：解析 HTML，輸出可調整的 Python POM 類別。
Page Object Model skeleton generator: parse HTML and emit a Python POM
class with locators + interaction methods. Output is a starting point that
should be reviewed/edited, not a final artefact.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional

import requests

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class POMGeneratorError(WebRunnerException):
    """Raised when POM generation cannot proceed."""


_INTERACTIVE_TAGS = {"input", "select", "textarea", "button", "a"}
_NAME_SANITISE = re.compile(r"[^A-Za-z0-9]+")
_LEADING_DIGIT = re.compile(r"^\d")


class _InteractiveElementCollector(HTMLParser):
    """Walk an HTML document and collect interactive elements."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: List[Dict[str, Optional[str]]] = []
        self._current_button_text: List[str] = []
        self._inside_button: bool = False

    def handle_starttag(self, tag: str, attrs):
        if tag not in _INTERACTIVE_TAGS:
            return
        attr_dict = dict(attrs)
        record: Dict[str, Optional[str]] = {
            "tag": tag,
            "id": attr_dict.get("id"),
            "name": attr_dict.get("name"),
            "type": attr_dict.get("type"),
            "class": attr_dict.get("class"),
            "href": attr_dict.get("href"),
            "placeholder": attr_dict.get("placeholder"),
            "text": None,
        }
        if tag == "button":
            self._inside_button = True
            self._current_button_text = []
        self.elements.append(record)

    def handle_endtag(self, tag: str):
        if tag == "button" and self._inside_button:
            self._inside_button = False
            text = "".join(self._current_button_text).strip()
            if self.elements and self.elements[-1]["tag"] == "button":
                self.elements[-1]["text"] = text or None
            self._current_button_text = []

    def handle_data(self, data: str):
        if self._inside_button:
            self._current_button_text.append(data)


def extract_elements_from_html(html: str) -> List[Dict[str, Optional[str]]]:
    """Parse ``html`` and return a list of interactive element dicts."""
    parser = _InteractiveElementCollector()
    parser.feed(html)
    parser.close()
    return parser.elements


def _safe_method_name(prefix: str, candidate: str, used: set) -> str:
    base = _NAME_SANITISE.sub("_", candidate or "").strip("_").lower() or "element"
    if _LEADING_DIGIT.match(base):
        base = f"_{base}"
    name = f"{prefix}_{base}"
    counter = 1
    while name in used:
        counter += 1
        name = f"{prefix}_{base}_{counter}"
    used.add(name)
    return name


def _locator_for(element: Dict[str, Optional[str]]):
    """Return a (strategy, value) tuple suitable for TestObject."""
    if element.get("id"):
        return ("ID", element["id"])
    if element.get("name"):
        return ("NAME", element["name"])
    if element.get("class"):
        first_class = element["class"].split()[0]
        return ("CLASS_NAME", first_class)
    if element.get("text"):
        return ("LINK_TEXT", element["text"])
    return None


def _hint_for(element: Dict[str, Optional[str]]) -> str:
    return (
        element.get("id")
        or element.get("name")
        or element.get("text")
        or element.get("placeholder")
        or element.get("href")
        or element.get("class")
        or element.get("tag")
        or "element"
    )


def _action_kind(element: Dict[str, Optional[str]]) -> str:
    """Decide whether to scaffold a click or an input method."""
    tag = element.get("tag")
    type_attr = (element.get("type") or "").lower()
    if tag == "input" and type_attr in {"text", "email", "password", "tel", "search", "url", ""}:
        return "input"
    if tag == "textarea":
        return "input"
    if tag == "select":
        return "select"
    return "click"


_PASS_BODY = "        pass"


def _render_method(method_name: str, kind: str, locator_constant: str) -> List[str]:
    register_todo = "        # TODO: register self." + locator_constant + " as a TestObject before calling."
    if kind == "input":
        return [
            f"    def {method_name}(self, value: str) -> None:",
            f"        \"\"\"Type ``value`` into the {method_name[len('input_to_'):]} field.\"\"\"",
            register_todo,
            _PASS_BODY,
            "",
        ]
    if kind == "select":
        return [
            f"    def {method_name}(self, value: str) -> None:",
            "        # TODO: hook up to your dropdown helper.",
            _PASS_BODY,
            "",
        ]
    return [
        f"    def {method_name}(self) -> None:",
        f"        \"\"\"Click the {method_name[len('click_'):]} element.\"\"\"",
        register_todo,
        _PASS_BODY,
        "",
    ]


def _prefix_for(kind: str) -> str:
    """Return the method-name prefix for a given action kind."""
    if kind == "input":
        return "input_to"
    if kind == "select":
        return "select_in"
    return "click"


def generate_pom_class(class_name: str, elements: List[Dict[str, Optional[str]]]) -> str:
    """
    產生 POM Python 類別原始碼
    Render Python source for a POM class with one constant + method per element.
    """
    used_constants: set = set()
    used_methods: set = set()
    constants: List[str] = []
    methods: List[str] = []
    for element in elements:
        locator = _locator_for(element)
        if locator is None:
            continue
        hint = _hint_for(element)
        kind = _action_kind(element)
        const_base = _NAME_SANITISE.sub("_", str(hint)).strip("_").upper() or "ELEMENT"
        if _LEADING_DIGIT.match(const_base):
            const_base = f"_{const_base}"
        const_name = const_base
        counter = 1
        while const_name in used_constants:
            counter += 1
            const_name = f"{const_base}_{counter}"
        used_constants.add(const_name)
        constants.append(f"    {const_name} = ({locator[0]!r}, {locator[1]!r})")

        method_name = _safe_method_name(_prefix_for(kind), str(hint), used_methods)
        methods.extend(_render_method(method_name, kind, const_name))

    if not constants:
        constants.append("    # no interactive elements detected")
    if not methods:
        methods.append("    # no methods generated")

    lines = [
        f"class {class_name}:",
        f"    \"\"\"Generated POM skeleton for {class_name}. Review before use.\"\"\"",
        "",
        *constants,
        "",
        "    def __init__(self, runner) -> None:",
        "        self.runner = runner",
        "",
        *methods,
    ]
    return "\n".join(lines).rstrip() + "\n"


def generate_pom_from_html(html: str, class_name: str) -> str:
    """Convenience: parse HTML and render the POM class in one call."""
    elements = extract_elements_from_html(html)
    return generate_pom_class(class_name, elements)


def generate_pom_from_url(url: str, class_name: str, timeout: int = 30) -> str:
    """
    從 URL 下載 HTML 並產生 POM 類別
    Fetch the URL and emit a POM class. ``http`` / ``https`` schemes only.
    """
    if not isinstance(url, str) or not (url.startswith("http://") or url.startswith("https://")):  # NOSONAR — scheme allow-list, not an outbound HTTP call
        raise POMGeneratorError(f"URL must be http(s): {url!r}")
    web_runner_logger.info(f"generate_pom_from_url: {url}")
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return generate_pom_from_html(response.text, class_name)


def write_pom_to_file(source: str, output_path: str) -> str:
    """Write generated source to ``output_path``; returns the path written."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")
    return str(target)
