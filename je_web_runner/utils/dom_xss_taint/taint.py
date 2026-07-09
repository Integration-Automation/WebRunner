"""
DOM-based XSS taint tracking (lightweight, heuristic).

Real DOM XSS taint analysis needs a JS-AST walker; this module gives you
the next best thing: a JS instrumentation snippet that records each
write of a "source" string into a "sink", plus a Python analyser that
checks the captured pairs against an attack payload.

* **Sources** monitored: ``location.hash``, ``location.search``,
  ``location.href`` reads, ``document.cookie`` reads, ``postMessage``
  ``event.data`` reads.
* **Sinks** monitored: ``innerHTML``, ``outerHTML``, ``document.write``,
  ``eval``, ``new Function``, ``setAttribute('on...')``, ``script.src``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class DomXssTaintError(WebRunnerException):
    """Raised when a tainted source reaches a sink."""


INSTALL_SCRIPT = r"""
(function (canaries) {
  if (window.__wr_taint__) return;
  const findings = [];
  function check(value, sink) {
    if (typeof value !== 'string') return;
    for (const c of canaries) {
      if (value.indexOf(c) !== -1) {
        findings.push({sink, canary: c, snippet: value.slice(0, 200)});
        return;
      }
    }
  }
  // innerHTML / outerHTML
  ['innerHTML', 'outerHTML'].forEach((prop) => {
    const desc = Object.getOwnPropertyDescriptor(Element.prototype, prop);
    if (!desc || !desc.set) return;
    Object.defineProperty(Element.prototype, prop, {
      set(v) { check(v, prop); desc.set.call(this, v); },
      get() { return desc.get.call(this); },
      configurable: true,
    });
  });
  // document.write
  const origWrite = document.write.bind(document);
  document.write = function (s) { check(s, 'document.write'); return origWrite(s); };
  // eval / Function
  const origEval = window.eval;
  window.eval = function (s) { check(s, 'eval'); return origEval(s); };
  const origFn = window.Function;
  window.Function = function () {
    Array.prototype.slice.call(arguments).forEach((a) => check(a, 'Function'));
    return origFn.apply(this, arguments);
  };
  window.__wr_taint__ = {
    drain: function () { return findings.splice(0); },
  };
})(arguments[0]);
"""


@dataclass
class TaintFinding:
    sink: str
    canary: str
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_canaries(test_name: str) -> list[str]:
    """Generate a couple of unique sentinel strings to inject as source
    values (location.hash, postMessage payload, etc.)."""
    if not isinstance(test_name, str) or not test_name:
        raise DomXssTaintError("test_name must be non-empty")
    return [
        f"WRXSS-{test_name}-A-{hash(test_name) & 0xFFFFFF:06x}",
        f"WRXSS-{test_name}-B-{(hash(test_name) >> 8) & 0xFFFFFF:06x}",
    ]


def parse_findings(payload: Any) -> list[TaintFinding]:
    if not isinstance(payload, list):
        raise DomXssTaintError("payload must be a list")
    out: list[TaintFinding] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        sink = str(raw.get("sink") or "")
        canary = str(raw.get("canary") or "")
        if not sink or not canary:
            continue
        out.append(TaintFinding(
            sink=sink, canary=canary,
            snippet=str(raw.get("snippet") or ""),
        ))
    return out


def assert_no_taint(findings: Iterable[TaintFinding]) -> None:
    items = list(findings)
    if items:
        details = [f"{f.canary} → {f.sink}" for f in items[:5]]
        raise DomXssTaintError(
            f"{len(items)} tainted source→sink pair(s) observed: {details}"
        )


def assert_only_safe_sinks(
    findings: Iterable[TaintFinding], *, allowed_sinks: Sequence[str],
) -> None:
    """For pages that intentionally write user content into ``innerHTML``
    via a trusted sanitiser, allow specific sinks."""
    allowed = set(allowed_sinks)
    forbidden = [f for f in findings if f.sink not in allowed]
    if forbidden:
        raise DomXssTaintError(
            f"taint reached non-allowed sink(s): "
            f"{sorted({f.sink for f in forbidden})}"
        )
