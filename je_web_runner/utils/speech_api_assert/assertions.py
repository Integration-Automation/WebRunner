"""
Web Speech API mock + assertion helpers.

Tests covering voice flows hit two flaky walls:

* Real ``SpeechRecognition`` (Chromium-only, network-dependent) is too
  unreliable for CI.
* ``SpeechSynthesis`` queues are global and bleed between tests.

This module ships an ``INSTALL_SCRIPT`` that:

* Replaces ``window.SpeechRecognition`` with a deterministic mock the
  test driver can push transcripts into.
* Records every ``speechSynthesis.speak`` utterance (text, lang, rate,
  pitch) for inspection from Python.

Python-side helpers parse the captured calls and provide focused
assertions: ``assert_spoke``, ``assert_lang``, ``assert_no_speech``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SpeechApiAssertError(WebRunnerException):
    """Raised when a speech-API invariant fails."""


INSTALL_SCRIPT = r"""
(function () {
  if (window.__wr_speech__) return;
  const spoken = [];
  const recognitionResults = [];
  // SpeechSynthesis interception
  const origSpeak = window.speechSynthesis &&
    window.speechSynthesis.speak.bind(window.speechSynthesis);
  if (window.speechSynthesis) {
    window.speechSynthesis.speak = function (u) {
      spoken.push({text: u.text, lang: u.lang, rate: u.rate,
                   pitch: u.pitch, volume: u.volume});
      if (origSpeak) try { origSpeak(u); } catch (_) {}
    };
  }
  // Mock SpeechRecognition
  function MockRecognition() {
    this.lang = 'en-US'; this.continuous = false;
  }
  MockRecognition.prototype.start = function () {
    this.onaudiostart && this.onaudiostart({});
    this.onresult && this.onresult({results: [[
      {transcript: recognitionResults.shift() || '', confidence: 1.0,
       isFinal: true}
    ]]});
    this.onend && this.onend({});
  };
  MockRecognition.prototype.stop = function () {};
  window.SpeechRecognition = MockRecognition;
  window.webkitSpeechRecognition = MockRecognition;
  window.__wr_speech__ = {
    drainSpoken: function () { return spoken.splice(0); },
    pushTranscript: function (t) { recognitionResults.push(t); },
  };
})();
"""


@dataclass
class Utterance:
    text: str = ""
    lang: str = ""
    rate: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_spoken(payload: Any) -> List[Utterance]:
    if not isinstance(payload, list):
        raise SpeechApiAssertError("payload must be a list")
    out: List[Utterance] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        out.append(Utterance(
            text=str(raw.get("text") or ""),
            lang=str(raw.get("lang") or ""),
            rate=float(raw.get("rate") or 1.0),
            pitch=float(raw.get("pitch") or 1.0),
            volume=float(raw.get("volume") or 1.0),
        ))
    return out


def assert_spoke(
    utterances: Iterable[Utterance],
    *, text_contains: str,
) -> Utterance:
    if not text_contains:
        raise SpeechApiAssertError("text_contains must be non-empty")
    for u in utterances:
        if text_contains in u.text:
            return u
    raise SpeechApiAssertError(
        f"no utterance contained {text_contains!r}"
    )


def assert_lang(
    utterances: Iterable[Utterance], *, expected_lang: str,
) -> None:
    if not expected_lang:
        raise SpeechApiAssertError("expected_lang must be non-empty")
    wrong = [u for u in utterances
             if u.lang and u.lang != expected_lang]
    if wrong:
        actual = {u.lang for u in wrong}
        raise SpeechApiAssertError(
            f"utterances spoke in {actual}, expected {expected_lang!r}"
        )


def assert_no_speech(utterances: Iterable[Utterance]) -> None:
    items = list(utterances)
    if items:
        previews = [u.text[:40] for u in items[:3]]
        raise SpeechApiAssertError(
            f"expected no speech, got {len(items)} utterance(s) "
            f"e.g. {previews}"
        )


def assert_within_volume(
    utterances: Iterable[Utterance], *, min_volume: float, max_volume: float,
) -> None:
    if not 0 <= min_volume <= max_volume <= 1:
        raise SpeechApiAssertError(
            "volume bounds must satisfy 0<=min<=max<=1"
        )
    bad = [u for u in utterances
           if not min_volume <= u.volume <= max_volume]
    if bad:
        raise SpeechApiAssertError(
            f"{len(bad)} utterance(s) outside volume band "
            f"[{min_volume}, {max_volume}]"
        )
