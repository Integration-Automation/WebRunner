"""
Web Serial API mock — emulate a UART so tests can stream lines into a
page and observe what the page writes back.

* ``INSTALL_SCRIPT`` overrides ``navigator.serial`` with a single
  fake port whose readable/writable are connected to in-memory queues
  the test driver can poke.
* Python helpers: ``build_mock_port``, ``encode_lines``, and assertion
  ``assert_lines_written`` to validate the page's writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebserialMockError(WebRunnerException):
    """Raised on malformed input or assertion failure."""


INSTALL_SCRIPT = r"""
(function (port) {
  if (window.__wr_serial__) return;
  const inboundQ = [];     // bytes queued by the test for the page to read
  const outbound = [];     // bytes the page wrote
  let openOpts = null;
  let readResolver = null;
  function drainInboundOnce() {
    if (readResolver && inboundQ.length) {
      const chunk = inboundQ.shift();
      readResolver({value: new Uint8Array(chunk), done: false});
      readResolver = null;
    }
  }
  const reader = {
    read: function () {
      return new Promise((resolve) => {
        readResolver = resolve;
        drainInboundOnce();
      });
    },
    cancel: async function () { readResolver = null; },
    releaseLock: function () {},
  };
  const writer = {
    write: async function (data) {
      outbound.push(Array.from(new Uint8Array(data)));
    },
    close: async function () {},
    releaseLock: function () {},
  };
  const fake = {
    open: async function (opts) { openOpts = opts; },
    close: async function () { openOpts = null; },
    get readable() { return {getReader: () => reader}; },
    get writable() { return {getWriter: () => writer}; },
    info: port,
  };
  navigator.serial = {
    requestPort: async () => fake,
    getPorts: async () => [fake],
  };
  window.__wr_serial__ = {
    pushInbound: function (bytes) {
      inboundQ.push(bytes);
      drainInboundOnce();
    },
    drainOutbound: function () { return outbound.splice(0); },
    openOpts: function () { return openOpts; },
  };
})(arguments[0]);
"""


@dataclass
class MockSerialPort:
    vendor_id: Optional[int] = None
    product_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_mock_port(
    vendor_id: Optional[int] = None, product_id: Optional[int] = None,
) -> MockSerialPort:
    for tag, value in (("vendor", vendor_id), ("product", product_id)):
        if value is not None and not 0 <= value <= 0xFFFF:
            raise WebserialMockError(f"{tag} id must fit in uint16")
    return MockSerialPort(vendor_id=vendor_id, product_id=product_id)


def encode_lines(lines: Sequence[str], newline: str = "\n") -> List[int]:
    if not isinstance(lines, (list, tuple)):
        raise WebserialMockError("lines must be a sequence of str")
    if not isinstance(newline, str):
        raise WebserialMockError("newline must be a string")
    out: List[int] = []
    for line in lines:
        if not isinstance(line, str):
            raise WebserialMockError("each line must be string")
        out.extend((line + newline).encode("utf-8"))
    return out


def parse_outbound(payload: Any) -> List[bytes]:
    if not isinstance(payload, list):
        raise WebserialMockError("payload must be a list")
    out: List[bytes] = []
    for raw in payload:
        if not isinstance(raw, list):
            continue
        out.append(bytes(int(b) for b in raw))
    return out


def assert_lines_written(
    chunks: Iterable[bytes], *, expected: Sequence[str], newline: str = "\n",
) -> None:
    joined = b"".join(chunks).decode("utf-8", errors="replace")
    actual = [l for l in joined.split(newline) if l != ""]
    if actual != list(expected):
        raise WebserialMockError(
            f"line mismatch: expected {list(expected)}, got {actual}"
        )
