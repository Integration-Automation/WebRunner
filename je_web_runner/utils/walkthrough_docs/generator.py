"""
AI 走查文件產生器:從跑過的 test(actions + screenshots)生 step-by-step
markdown SOP / onboarding 教學,也能直接輸出 Confluence storage XHTML。

Pipeline:

1. ``collect_steps`` — pair each non-trivial action with the screenshot
   captured immediately after it (when available). Skips utility actions
   (set_timeout, sleep, no-ops).
2. ``narrate_steps`` — call the LLM with the action list + meta and ask
   for one-sentence end-user-facing narration per step.
3. ``render_markdown`` / ``render_confluence`` — produce final docs with
   per-step screenshots embedded as base64 data URIs (markdown) or
   ``<ac:image><ri:attachment/>`` placeholders (Confluence).
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from je_web_runner.utils.ai_assist.llm_assist import LLMAssistError, _invoke
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class WalkthroughError(WebRunnerException):
    """Raised on invalid inputs or LLM output."""


# Actions that are noise from a documentation perspective
_NOISE_PREFIXES = (
    "WR_set_", "WR_sleep", "WR_pause", "WR_init", "WR_quit",
    "WR_save_test_object", "WR_callback_", "WR_wait_for_timeout",
)


# ---------- data ---------------------------------------------------------

@dataclass
class WalkthroughStep:
    """One step in the generated walkthrough."""

    index: int
    action_command: str
    narration: str = ""
    summary: str = ""
    kwargs: Dict[str, Any] = field(default_factory=dict)
    screenshot_path: Optional[str] = None
    screenshot_b64: Optional[str] = None
    screenshot_mime: str = "image/png"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Walkthrough:
    """A bundle of steps for one test."""

    title: str
    description: str = ""
    steps: List[WalkthroughStep] = field(default_factory=list)
    audience: str = "end-user"  # "end-user" | "developer" | "support"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "audience": self.audience,
            "steps": [s.to_dict() for s in self.steps],
        }


# ---------- collection --------------------------------------------------

def collect_steps(
    actions: Sequence[Any],
    *,
    screenshots: Optional[Dict[int, Union[str, Path, bytes]]] = None,
    skip_noise: bool = True,
) -> List[WalkthroughStep]:
    """
    把 action list 變成 walkthrough step。``screenshots`` 可選擇用 action
    index → 檔案路徑 / bytes 來附對應截圖。
    """
    if not isinstance(actions, (list, tuple)):
        raise WalkthroughError(
            f"actions must be a sequence, got {type(actions).__name__}"
        )
    screenshots = screenshots or {}
    steps: List[WalkthroughStep] = []
    for idx, action in enumerate(actions):
        if not isinstance(action, list) or not action:
            continue
        command = action[0] if isinstance(action[0], str) else ""
        if not command:
            continue
        if skip_noise and any(command.startswith(p) for p in _NOISE_PREFIXES):
            continue
        kwargs = _extract_kwargs(action)
        step = WalkthroughStep(
            index=idx,
            action_command=command,
            kwargs=kwargs,
        )
        screenshot = screenshots.get(idx)
        if screenshot is not None:
            _attach_screenshot(step, screenshot)
        steps.append(step)
    return steps


def _extract_kwargs(action: List[Any]) -> Dict[str, Any]:
    if len(action) >= 3 and isinstance(action[2], dict):
        return action[2]
    if len(action) >= 2 and isinstance(action[1], dict):
        return action[1]
    return {}


def _attach_screenshot(
    step: WalkthroughStep, source: Union[str, Path, bytes],
) -> None:
    if isinstance(source, (bytes, bytearray)):
        step.screenshot_b64 = base64.b64encode(bytes(source)).decode("ascii")
        step.screenshot_path = None
        return
    path = Path(source)
    if not path.is_file():
        web_runner_logger.warning(
            f"_attach_screenshot: file not found, skipping: {path}"
        )
        return
    step.screenshot_path = str(path)
    try:
        step.screenshot_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError as error:
        web_runner_logger.warning(f"_attach_screenshot read failed: {error!r}")
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        step.screenshot_mime = "image/jpeg"
    elif suffix == ".webp":
        step.screenshot_mime = "image/webp"
    else:
        step.screenshot_mime = "image/png"


# ---------- LLM narration ------------------------------------------------

_NARRATE_PROMPT = (
    "You are writing customer-facing step-by-step documentation. For "
    "each step below, produce a single short sentence describing what "
    "the user is doing — write for a {audience}. Output ONLY a JSON "
    "object with one key 'steps' whose value is a list of strings in "
    "the same order. No prose.\n\n"
    "Test title: {title}\n"
    "Steps (commands + key kwargs):\n{steps}\n"
)


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _summarise_kwargs(kwargs: Dict[str, Any]) -> str:
    """Print kwargs compactly for the prompt — drop verbose payloads."""
    out: Dict[str, Any] = {}
    for key in ("url", "test_object_name", "text", "value", "expected", "selector"):
        if key in kwargs:
            val = kwargs[key]
            if isinstance(val, str) and len(val) > 80:
                val = val[:77] + "…"
            out[key] = val
    return json.dumps(out, ensure_ascii=False)


def narrate_steps(
    walkthrough: Walkthrough,
    *,
    audience: Optional[str] = None,
) -> Walkthrough:
    """
    呼叫 LLM 對每個 step 補一句敘述。原 Walkthrough 物件被就地更新並回傳。
    """
    if not walkthrough.steps:
        return walkthrough
    aud = audience or walkthrough.audience or "end-user"
    walkthrough.audience = aud
    lines = []
    for s in walkthrough.steps:
        lines.append(f"  {s.index}. {s.action_command}({_summarise_kwargs(s.kwargs)})")
    prompt = _NARRATE_PROMPT.format(
        audience=aud, title=walkthrough.title, steps="\n".join(lines),
    )
    try:
        raw = _invoke(prompt)
    except LLMAssistError as error:
        raise WalkthroughError(str(error)) from error
    payload = _parse_payload(raw)
    narrations = payload.get("steps")
    if not isinstance(narrations, list):
        raise WalkthroughError("LLM payload missing 'steps' list")
    for step, narration in zip(walkthrough.steps, narrations):
        step.narration = str(narration or "").strip()
    web_runner_logger.info(
        f"narrate_steps: title={walkthrough.title!r} steps={len(walkthrough.steps)}"
    )
    return walkthrough


def _parse_payload(text: str) -> Dict[str, Any]:
    match = _JSON_OBJECT_RE.search(text)
    if match is None:
        raise WalkthroughError("LLM did not return a JSON object")
    try:
        return json.loads(match.group(0))
    except ValueError as error:
        raise WalkthroughError(f"LLM JSON did not parse: {error}") from error


# ---------- rendering ---------------------------------------------------

def render_markdown(walkthrough: Walkthrough, *, embed_images: bool = True) -> str:
    """
    Markdown 走查文件。截圖內嵌成 data URI(``embed_images=False`` 時改用路徑)。
    """
    pieces = [
        f"# {walkthrough.title or 'Walkthrough'}",
        "",
    ]
    if walkthrough.description:
        pieces.append(walkthrough.description)
        pieces.append("")
    pieces.append(f"_Audience: {walkthrough.audience}_")
    pieces.append("")
    for i, step in enumerate(walkthrough.steps, 1):
        narration = step.narration or step.summary or _fallback_narration(step)
        pieces.append(f"## Step {i}. {narration}")
        pieces.append("")
        pieces.append(f"`{step.action_command}` — {_summarise_kwargs(step.kwargs)}")
        pieces.append("")
        if step.screenshot_b64 and embed_images:
            data_uri = f"data:{step.screenshot_mime};base64,{step.screenshot_b64}"
            pieces.append(f"![Step {i} screenshot]({data_uri})")
            pieces.append("")
        elif step.screenshot_path:
            pieces.append(f"![Step {i} screenshot]({step.screenshot_path})")
            pieces.append("")
    return "\n".join(pieces).rstrip() + "\n"


def render_confluence(walkthrough: Walkthrough) -> str:
    """
    Confluence storage 格式(XHTML),用 ``<ac:image>`` + ``<ri:attachment>``。
    Caller is responsible for uploading screenshots as attachments first.
    """
    pieces: List[str] = [
        f"<h1>{_xml_escape(walkthrough.title or 'Walkthrough')}</h1>",
    ]
    if walkthrough.description:
        pieces.append(f"<p>{_xml_escape(walkthrough.description)}</p>")
    pieces.append(f"<p><em>Audience: {_xml_escape(walkthrough.audience)}</em></p>")
    for i, step in enumerate(walkthrough.steps, 1):
        narration = step.narration or step.summary or _fallback_narration(step)
        pieces.append(f"<h2>Step {i}. {_xml_escape(narration)}</h2>")
        pieces.append(
            f"<p><code>{_xml_escape(step.action_command)}</code> — "
            f"{_xml_escape(_summarise_kwargs(step.kwargs))}</p>"
        )
        if step.screenshot_path:
            fname = Path(step.screenshot_path).name
            pieces.append(
                f'<ac:image><ri:attachment ri:filename="{_xml_escape(fname)}"/></ac:image>'
            )
    return "\n".join(pieces) + "\n"


def _fallback_narration(step: WalkthroughStep) -> str:
    return f"({step.action_command})"


def _xml_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


# ---------- one-shot convenience ----------------------------------------

def build_walkthrough(
    title: str,
    actions: Sequence[Any],
    *,
    description: str = "",
    audience: str = "end-user",
    screenshots: Optional[Dict[int, Union[str, Path, bytes]]] = None,
    narrate: bool = True,
) -> Walkthrough:
    """
    讀 actions → 收集 steps → (可選)呼 LLM 加敘述。
    Returns a :class:`Walkthrough` ready to render. ``narrate=False``
    yields a doc with empty narrations — useful when no LLM is available.
    """
    walkthrough = Walkthrough(
        title=title or "Walkthrough",
        description=description,
        audience=audience,
        steps=collect_steps(actions, screenshots=screenshots),
    )
    if narrate:
        narrate_steps(walkthrough)
    return walkthrough


def save_walkthrough(
    walkthrough: Walkthrough,
    output_path: Union[str, Path],
    *,
    fmt: str = "markdown",
) -> Path:
    """Persist the walkthrough as ``markdown`` (default) or ``confluence``."""
    if fmt not in {"markdown", "confluence"}:
        raise WalkthroughError(f"unsupported fmt {fmt!r}")
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        render_markdown(walkthrough)
        if fmt == "markdown"
        else render_confluence(walkthrough)
    )
    path.write_text(text, encoding="utf-8")
    web_runner_logger.info(f"save_walkthrough: wrote {path} ({fmt})")
    return path
