"""
Selenium 寫法靜態翻譯成 Playwright：覆蓋常見 60-70% pattern。
Static (regex-based) translator for the most-used Selenium API calls and
WebRunner action JSON commands. Output is a draft — caller-supplied
review is still required, especially for:

- chained ActionChains / multi-step waits
- iframe / window switching (Playwright uses ``page.frame_locator``)
- file uploads (``send_keys`` ↔ ``set_input_files``)

For action JSON the translator rewrites well-known ``WR_*`` commands to
their ``WR_pw_*`` Playwright equivalents.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SelToPwError(WebRunnerException):
    """Raised on invalid input to the translator."""


@dataclass
class Translation:
    line: int
    original: str
    translated: str
    note: str = ""


_PYTHON_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    (re.compile(r"driver\.find_element\(By\.ID,\s*['\"]([^'\"]+)['\"]\)"),
     "page.locator('#\\1')",
     "ID -> CSS id selector"),
    (re.compile(r"driver\.find_element\(By\.CLASS_NAME,\s*['\"]([^'\"]+)['\"]\)"),
     "page.locator('.\\1')",
     "CLASS_NAME -> CSS class selector"),
    (re.compile(r"driver\.find_element\(By\.NAME,\s*['\"]([^'\"]+)['\"]\)"),
     "page.locator('[name=\"\\1\"]')",
     "NAME -> CSS [name=...]"),
    (re.compile(r"driver\.find_element\(By\.CSS_SELECTOR,\s*(['\"][^'\"]+['\"])\)"),
     "page.locator(\\1)",
     "CSS_SELECTOR -> page.locator()"),
    (re.compile(r"driver\.find_element\(By\.XPATH,\s*(['\"][^'\"]+['\"])\)"),
     "page.locator(f'xpath=' + \\1)",
     "XPATH -> page.locator(xpath=...)"),
    (re.compile(r"driver\.find_element\(By\.LINK_TEXT,\s*(['\"][^'\"]+['\"])\)"),
     "page.get_by_role('link', name=\\1)",
     "LINK_TEXT -> get_by_role('link', name=...)"),
    (re.compile(r"driver\.get\((['\"][^'\"]+['\"])\)"),
     "page.goto(\\1)",
     "driver.get -> page.goto"),
    (re.compile(r"driver\.implicitly_wait\(\d+\)"),
     "# Playwright auto-waits — drop implicitly_wait()",
     "implicit wait removed"),
    (re.compile(r"driver\.refresh\(\)"),
     "page.reload()",
     "refresh -> reload"),
    (re.compile(r"driver\.back\(\)"),
     "page.go_back()",
     "back -> go_back"),
    (re.compile(r"driver\.forward\(\)"),
     "page.go_forward()",
     "forward -> go_forward"),
    (re.compile(r"driver\.quit\(\)"),
     "page.context.close()",
     "driver.quit -> context.close"),
    (re.compile(r"\.send_keys\((['\"][^'\"]+['\"])\)"),
     ".fill(\\1)",
     "send_keys(text) -> fill(text)"),
    (re.compile(r"\.send_keys\(Keys\.ENTER\)"),
     ".press('Enter')",
     "send_keys(Keys.ENTER) -> press('Enter')"),
    (re.compile(r"\.click\(\)"),
     ".click()",
     "click() unchanged"),
    (re.compile(r"\.text(?![A-Za-z_])"),
     ".inner_text()",
     ".text -> .inner_text()"),
    (re.compile(r"WebDriverWait\(driver,\s*(\d+)\)\.until\(EC\.visibility_of_element_located"),
     "page.wait_for_selector(",
     "explicit wait -> wait_for_selector (timeout in ms)"),
]


def translate_python_source(source: str) -> List[Translation]:
    """Translate Python source line-by-line, returning a Translation per hit."""
    if not isinstance(source, str):
        raise SelToPwError("source must be str")
    translations: List[Translation] = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        translated = line
        notes: List[str] = []
        for pattern, replacement, note in _PYTHON_PATTERNS:
            new_text = pattern.sub(replacement, translated)
            if new_text != translated:
                notes.append(note)
                translated = new_text
        if translated != line:
            translations.append(Translation(
                line=line_no,
                original=line,
                translated=translated,
                note="; ".join(notes),
            ))
    return translations


_ACTION_COMMAND_MAP = {
    "WR_to_url": "WR_pw_to_url",
    "WR_element_click": "WR_pw_click",
    "WR_element_input": "WR_pw_fill",
    "WR_implicitly_wait": None,  # drop entirely; Playwright auto-waits
    "WR_refresh": "WR_pw_reload",
    "WR_back": "WR_pw_go_back",
    "WR_forward": "WR_pw_go_forward",
    "WR_quit_all": "WR_pw_close_context",
    "WR_get_screenshot_as_png": "WR_pw_screenshot_png",
    "WR_set_window_size": "WR_pw_set_viewport_size",
}


def translate_action_list(actions: List[Any]) -> List[List[Any]]:
    """
    把 ``WR_*`` action 清單翻譯成 Playwright 變體；無對應時保留原本的指令並加註。
    Translate a WebRunner action list. ``WR_implicitly_wait`` is dropped
    silently; commands without a registered mapping survive intact so the
    output remains a runnable draft.
    """
    if not isinstance(actions, list):
        raise SelToPwError("actions must be a list")
    translated: List[List[Any]] = []
    for action in actions:
        if not isinstance(action, list) or not action:
            translated.append(action)
            continue
        command = action[0]
        if not isinstance(command, str):
            translated.append(action)
            continue
        if command not in _ACTION_COMMAND_MAP:
            translated.append(list(action))
            continue
        new_command = _ACTION_COMMAND_MAP[command]
        if new_command is None:
            continue  # drop
        new_action = list(action)
        new_action[0] = new_command
        translated.append(new_action)
    return translated


def supported_python_patterns() -> List[str]:
    return [pat.pattern for pat, _replacement, _note in _PYTHON_PATTERNS]


def supported_action_commands() -> List[str]:
    return sorted(_ACTION_COMMAND_MAP.keys())
