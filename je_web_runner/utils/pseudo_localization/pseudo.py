"""
字串 → pseudo-localised 變體,專抓 hard-coded text、截斷、RTL bug。
Classic trick: translate "Sign in" → "[!! Šîgñ în ──]". A real engineer
glancing at the page can tell which strings *weren't* translated (still
ASCII) and which UI elements truncate when text grows ~40%.

Three independent transforms (toggleable):

* **accent_map** — ASCII letters → look-alike Unicode (still readable).
* **expansion** — pad the string to simulate longer translations.
* **bracket** — wrap with markers to make untranslated leakage obvious.

Plus a tiny scanner that diffs original vs pseudo and flags strings that
came back unchanged (= probably hard-coded, not from i18n catalogue).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PseudoLocalizationError(WebRunnerException):
    """Raised on invalid config or string input."""


_ACCENT_MAP: Mapping[str, str] = {
    "a": "ä", "b": "ƀ", "c": "ç", "d": "ð", "e": "é", "f": "ƒ", "g": "ğ",
    "h": "ĥ", "i": "î", "j": "ĵ", "k": "ķ", "l": "ł", "m": "ɱ", "n": "ñ",
    "o": "ö", "p": "þ", "q": "ǫ", "r": "ŕ", "s": "š", "t": "ţ", "u": "ü",
    "v": "ṽ", "w": "ŵ", "x": "ẋ", "y": "ÿ", "z": "ž",
    "A": "Ä", "B": "Ɓ", "C": "Ç", "D": "Ð", "E": "É", "F": "Ƒ", "G": "Ğ",
    "H": "Ĥ", "I": "Î", "J": "Ĵ", "K": "Ķ", "L": "Ł", "M": "Ṁ", "N": "Ñ",
    "O": "Ö", "P": "Þ", "Q": "Ǫ", "R": "Ŕ", "S": "Š", "T": "Ţ", "U": "Ü",
    "V": "Ṽ", "W": "Ŵ", "X": "Ẋ", "Y": "Ÿ", "Z": "Ž",
}

_PADDING_CHAR = "─"

_PLACEHOLDER_RE = re.compile(
    r"\{[^}]+\}"                 # {name}, {0}
    r"|%(?:\([^)]+\))?[diouxXeEfFgGcrs%]"  # printf-style
    r"|%[a-zA-Z]"                # %d, %s
    r"|<[^>]+>"                  # <span>, <br/>
)


# ---------- transforms --------------------------------------------------

@dataclass
class PseudoConfig:
    """Knobs for :func:`pseudo_localize`."""

    accent: bool = True
    expansion_ratio: float = 0.4  # 40% padding
    bracket: bool = True
    left_marker: str = "⟦"
    right_marker: str = "⟧"
    preserve_placeholders: bool = True

    def __post_init__(self) -> None:
        if self.expansion_ratio < 0:
            raise PseudoLocalizationError("expansion_ratio must be >= 0")
        if not isinstance(self.left_marker, str) or not isinstance(self.right_marker, str):
            raise PseudoLocalizationError("markers must be strings")


def _accent(text: str) -> str:
    return "".join(_ACCENT_MAP.get(ch, ch) for ch in text)


def _pad_to_ratio(text: str, ratio: float) -> str:
    if ratio <= 0 or not text:
        return text
    add = max(1, int(round(len(text) * ratio)))
    left = add // 2
    right = add - left
    return f"{_PADDING_CHAR * left} {text} {_PADDING_CHAR * right}"


def _split_around_placeholders(text: str) -> List[tuple]:
    """Return list of (segment, is_placeholder) tuples preserving order."""
    parts: List[tuple] = []
    last = 0
    for match in _PLACEHOLDER_RE.finditer(text):
        if match.start() > last:
            parts.append((text[last:match.start()], False))
        parts.append((match.group(0), True))
        last = match.end()
    if last < len(text):
        parts.append((text[last:], False))
    if not parts:
        parts.append((text, False))
    return parts


def pseudo_localize(
    text: str,
    config: Optional[PseudoConfig] = None,
) -> str:
    """Return a pseudo-localised version of ``text``."""
    if not isinstance(text, str):
        raise PseudoLocalizationError(
            f"pseudo_localize expects str, got {type(text).__name__}"
        )
    cfg = config or PseudoConfig()
    if not text:
        return text
    if cfg.preserve_placeholders:
        chunks: List[str] = []
        for segment, is_placeholder in _split_around_placeholders(text):
            if is_placeholder:
                chunks.append(segment)
            else:
                chunks.append(_accent(segment) if cfg.accent else segment)
        accented = "".join(chunks)
    else:
        accented = _accent(text) if cfg.accent else text
    padded = _pad_to_ratio(accented, cfg.expansion_ratio)
    if cfg.bracket:
        return f"{cfg.left_marker}{padded}{cfg.right_marker}"
    return padded


# ---------- bulk + JSON dict translation --------------------------------

def pseudo_localize_dict(
    catalogue: Mapping[str, str],
    config: Optional[PseudoConfig] = None,
) -> Dict[str, str]:
    """Apply :func:`pseudo_localize` to every value in a {key: string} map."""
    if not isinstance(catalogue, Mapping):
        raise PseudoLocalizationError("catalogue must be a mapping")
    out: Dict[str, str] = {}
    for key, value in catalogue.items():
        if not isinstance(value, str):
            raise PseudoLocalizationError(
                f"catalogue value for {key!r} must be str, got {type(value).__name__}"
            )
        out[key] = pseudo_localize(value, config)
    return out


# ---------- hard-coded string scanner -----------------------------------

@dataclass
class HardcodedHit:
    """One string that appeared verbatim in rendered output despite being pseudo'd."""

    string: str
    occurrences: int = 1


@dataclass
class PseudoAuditReport:
    """Roll-up of :func:`scan_for_hardcoded`."""

    rendered_chars: int = 0
    hits: List[HardcodedHit] = field(default_factory=list)

    def passed(self) -> bool:
        return not self.hits


def scan_for_hardcoded(
    rendered_text: str,
    *,
    catalogue: Mapping[str, str],
    min_length: int = 3,
) -> PseudoAuditReport:
    """
    Look for any catalogue value that still appears verbatim (i.e.
    untranslated) in ``rendered_text``. Strings shorter than
    ``min_length`` are ignored to cut noise from single letters /
    punctuation.
    """
    if not isinstance(rendered_text, str):
        raise PseudoLocalizationError("rendered_text must be str")
    if min_length < 1:
        raise PseudoLocalizationError("min_length must be >= 1")
    report = PseudoAuditReport(rendered_chars=len(rendered_text))
    seen: Dict[str, int] = {}
    for value in catalogue.values():
        if not isinstance(value, str) or len(value) < min_length:
            continue
        if not _contains_ascii_letters(value):
            continue
        count = rendered_text.count(value)
        if count > 0:
            seen[value] = seen.get(value, 0) + count
    for string, occurrences in sorted(seen.items(), key=lambda kv: -kv[1]):
        report.hits.append(HardcodedHit(string=string, occurrences=occurrences))
    return report


def _contains_ascii_letters(value: str) -> bool:
    return any(ch.isascii() and ch.isalpha() for ch in value)
