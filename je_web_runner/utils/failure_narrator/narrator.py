"""
LLM 從 failure_bundle 寫出自然語言的「為什麼這個 test 失敗了」報告。
Different from ``failure_triage`` (root-cause analysis with hypotheses):
this is the *human-friendly summary* you want in a PR comment or Slack
thread. "Login test failed because the submit button wasn't visible —
likely because feature flag `new_login_ui` was on for this PR."

The LLM client is abstracted so tests can stub responses; the prompt
template is exported so teams can tune tone without forking.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FailureNarratorError(WebRunnerException):
    """Raised on missing bundle, malformed input, or LLM client failure."""


# ---------- bundle inputs ----------------------------------------------

@dataclass
class FailureBundle:
    """Pre-digested failure facts used to build the prompt."""

    test_id: str
    action: str = ""
    error_message: str = ""
    error_class: str = ""
    last_url: str = ""
    last_dom_excerpt: str = ""
    console_errors: List[str] = field(default_factory=list)
    network_errors: List[str] = field(default_factory=list)
    failed_assertion: str = ""
    git_commit: str = ""
    flake_history: str = ""  # e.g. "flaky in 3/10 recent runs"
    extra_context: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.test_id, str) or not self.test_id:
            raise FailureNarratorError("test_id must be non-empty string")


def load_bundle_dir(path: Union[str, Path]) -> FailureBundle:
    """Read a failure-bundle directory laid out as JSON + text files."""
    bundle_dir = Path(path)
    if not bundle_dir.exists() or not bundle_dir.is_dir():
        raise FailureNarratorError(f"bundle dir not found: {bundle_dir}")
    meta_path = bundle_dir / "meta.json"
    if not meta_path.exists():
        raise FailureNarratorError(f"bundle missing meta.json: {meta_path}")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise FailureNarratorError(f"meta.json not JSON: {error}") from error
    if not isinstance(meta, dict):
        raise FailureNarratorError("meta.json must be an object")
    test_id = meta.get("test_id") or meta.get("path") or bundle_dir.name
    if not isinstance(test_id, str) or not test_id:
        raise FailureNarratorError("bundle has no usable test_id")
    return FailureBundle(
        test_id=test_id,
        action=str(meta.get("action") or ""),
        error_message=str(meta.get("error_message") or ""),
        error_class=str(meta.get("error_class") or ""),
        last_url=str(meta.get("last_url") or ""),
        last_dom_excerpt=_read_text(bundle_dir / "dom.html", limit=2000),
        console_errors=_read_lines(bundle_dir / "console.log"),
        network_errors=_read_lines(bundle_dir / "network_errors.log"),
        failed_assertion=str(meta.get("failed_assertion") or ""),
        git_commit=str(meta.get("git_commit") or ""),
        flake_history=str(meta.get("flake_history") or ""),
        extra_context=[str(x) for x in meta.get("extra_context") or []],
    )


def _read_text(path: Path, *, limit: int) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:limit]


def _read_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    return [line.rstrip("\n") for line in path.read_text(
        encoding="utf-8", errors="replace",
    ).splitlines() if line.strip()]


# ---------- LLM client protocol ----------------------------------------

class NarratorClient(Protocol):
    """The LLM client interface."""

    def complete(self, prompt: str) -> str: ...


# ---------- prompt ------------------------------------------------------

PROMPT_TEMPLATE = """\
You are an SRE assistant explaining why an end-to-end test failed.
Write a concise, factual, blame-free report.

# Failure facts
- Test: {test_id}
- Failing action: {action}
- Error: {error_class}: {error_message}
- Last URL: {last_url}
- Failed assertion: {failed_assertion}
- Recent flake history: {flake_history}
- Git commit under test: {git_commit}

# Console errors (sampled)
{console_errors}

# Network errors (sampled)
{network_errors}

# DOM excerpt (first 2k chars)
```
{last_dom_excerpt}
```

# Extra context
{extra_context}

# Instructions
Return strictly a JSON object with keys:
- "summary": one sentence
- "likely_cause": one or two sentences
- "next_step": one sentence with what an engineer should investigate first
- "confidence": "low" | "medium" | "high"
"""


def build_prompt(bundle: FailureBundle) -> str:
    """Render the deterministic prompt for the LLM."""
    if not isinstance(bundle, FailureBundle):
        raise FailureNarratorError("build_prompt expects FailureBundle")
    return PROMPT_TEMPLATE.format(
        test_id=bundle.test_id,
        action=bundle.action or "(unknown)",
        error_class=bundle.error_class or "Error",
        error_message=bundle.error_message or "(no message)",
        last_url=bundle.last_url or "(unknown)",
        failed_assertion=bundle.failed_assertion or "(none)",
        flake_history=bundle.flake_history or "(unknown)",
        git_commit=bundle.git_commit or "(unknown)",
        console_errors=_join_for_prompt(bundle.console_errors),
        network_errors=_join_for_prompt(bundle.network_errors),
        last_dom_excerpt=bundle.last_dom_excerpt or "(none captured)",
        extra_context=_join_for_prompt(bundle.extra_context),
    )


def _join_for_prompt(lines: Sequence[str]) -> str:
    if not lines:
        return "(none)"
    return "\n".join(f"- {line}" for line in lines[:10])


# ---------- response parsing -------------------------------------------

@dataclass
class NarrationReport:
    """Parsed LLM response."""

    summary: str
    likely_cause: str
    next_step: str
    confidence: str
    raw: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def markdown(self) -> str:
        return (
            f"**Why this failed**: {self.summary}\n\n"
            f"**Likely cause** ({self.confidence}): {self.likely_cause}\n\n"
            f"**Next step**: {self.next_step}\n"
        )


def parse_response(raw: str) -> NarrationReport:
    """Decode the LLM's JSON envelope into a :class:`NarrationReport`."""
    if not isinstance(raw, str) or not raw.strip():
        raise FailureNarratorError("LLM returned empty response")
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise FailureNarratorError(f"no JSON object in response: {raw[:160]!r}")
    try:
        obj = json.loads(raw[start:end + 1])
    except ValueError as error:
        raise FailureNarratorError(
            f"response was not JSON ({error}): {raw[:160]!r}"
        ) from error
    if not isinstance(obj, dict):
        raise FailureNarratorError("response JSON must be an object")
    for field_name in ("summary", "likely_cause", "next_step", "confidence"):
        if field_name not in obj or not isinstance(obj[field_name], str):
            raise FailureNarratorError(f"response missing string {field_name!r}")
    confidence = obj["confidence"].strip().lower()
    if confidence not in ("low", "medium", "high"):
        raise FailureNarratorError(
            f"unknown confidence {confidence!r}; want low/medium/high"
        )
    return NarrationReport(
        summary=obj["summary"].strip(),
        likely_cause=obj["likely_cause"].strip(),
        next_step=obj["next_step"].strip(),
        confidence=confidence,
        raw=raw,
    )


# ---------- end-to-end -------------------------------------------------

def narrate(
    bundle: FailureBundle,
    client: NarratorClient,
) -> NarrationReport:
    """Build prompt → call LLM → parse → return."""
    prompt = build_prompt(bundle)
    try:
        raw = client.complete(prompt)
    except Exception as error:
        raise FailureNarratorError(
            f"narrator client failed: {error!r}"
        ) from error
    return parse_response(raw)
