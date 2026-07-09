"""
WebUSB mock — install navigator.usb shim with configurable control
transfers, bulk endpoints, and string-descriptor responses.

Provides:

* ``INSTALL_SCRIPT`` — JS shim covering ``requestDevice``, ``open``,
  ``selectConfiguration``, ``claimInterface``, ``controlTransferIn/Out``,
  ``transferIn/Out``.
* Python ``MockUsbDevice`` builder + helpers.
* Assertions for what the page actually sent over the wire.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebusbMockError(WebRunnerException):
    """Raised when input is malformed or assertions fail."""


INSTALL_SCRIPT = r"""
(function (devices) {
  if (window.__wr_usb__) return;
  const outgoing = [];   // controlTransferOut / transferOut calls
  const queued = {};     // queued IN responses per endpoint
  function FakeUsbDevice(spec) {
    Object.assign(this, spec);
    this.opened = false;
    this.configuration = null;
    this.claimed = new Set();
  }
  FakeUsbDevice.prototype.open = async function () { this.opened = true; };
  FakeUsbDevice.prototype.close = async function () { this.opened = false; };
  FakeUsbDevice.prototype.selectConfiguration = async function (n) {
    this.configuration = n;
  };
  FakeUsbDevice.prototype.claimInterface = async function (n) {
    this.claimed.add(n);
  };
  FakeUsbDevice.prototype.controlTransferIn = async function (s, len) {
    return {data: queued.controlIn ? new DataView(
      new Uint8Array(queued.controlIn.shift() || []).buffer) : null,
      status: 'ok'};
  };
  FakeUsbDevice.prototype.controlTransferOut = async function (s, data) {
    outgoing.push({kind: 'controlOut', setup: s,
      data: Array.from(new Uint8Array(data || []))});
    return {bytesWritten: data ? data.byteLength : 0, status: 'ok'};
  };
  FakeUsbDevice.prototype.transferIn = async function (ep, len) {
    const key = 'in_' + ep;
    return {data: queued[key] ? new DataView(
      new Uint8Array(queued[key].shift() || []).buffer) : null,
      status: 'ok'};
  };
  FakeUsbDevice.prototype.transferOut = async function (ep, data) {
    outgoing.push({kind: 'transferOut', endpoint: ep,
      data: Array.from(new Uint8Array(data))});
    return {bytesWritten: data.byteLength, status: 'ok'};
  };
  const fakeDevices = devices.map((d) => new FakeUsbDevice(d));
  navigator.usb = {
    requestDevice: async () => fakeDevices[0],
    getDevices: async () => fakeDevices,
  };
  window.__wr_usb__ = {
    queueIn: function (kind, bytes) {
      queued[kind] = queued[kind] || [];
      queued[kind].push(bytes);
    },
    drainOutgoing: function () { return outgoing.splice(0); },
    listDevices: function () { return fakeDevices.map((d) => ({
      vendorId: d.vendorId, productId: d.productId, opened: d.opened,
    })); },
  };
})(arguments[0]);
"""


@dataclass
class MockUsbDevice:
    vendor_id: int
    product_id: int
    product_name: str = ""
    serial_number: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_mock_device(
    vendor_id: int, product_id: int, *,
    product_name: str = "", serial_number: str = "",
) -> MockUsbDevice:
    if not 0 <= vendor_id <= 0xFFFF or not 0 <= product_id <= 0xFFFF:
        raise WebusbMockError("vendor/product id must fit in uint16")
    return MockUsbDevice(vendor_id=vendor_id, product_id=product_id,
                         product_name=product_name,
                         serial_number=serial_number)


@dataclass
class OutgoingCall:
    kind: str            # "controlOut" | "transferOut"
    endpoint: int | None = None
    setup: dict[str, Any] | None = None
    data: list[int] = field(default_factory=list)


def parse_outgoing(payload: Any) -> list[OutgoingCall]:
    if not isinstance(payload, list):
        raise WebusbMockError("payload must be a list")
    out: list[OutgoingCall] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        out.append(OutgoingCall(
            kind=str(raw.get("kind") or ""),
            endpoint=raw.get("endpoint"),
            setup=raw.get("setup"),
            data=[int(b) for b in (raw.get("data") or [])],
        ))
    return out


def assert_transfer_out(
    calls: Iterable[OutgoingCall],
    *, endpoint: int, contains: Sequence[int] | None = None,
) -> OutgoingCall:
    matches = [c for c in calls
               if c.kind == "transferOut" and c.endpoint == endpoint]
    if not matches:
        raise WebusbMockError(
            f"no transferOut on endpoint {endpoint}"
        )
    if contains is None:
        return matches[0]
    needle = list(contains)
    for c in matches:
        if any(c.data[i:i + len(needle)] == needle
               for i in range(len(c.data) - len(needle) + 1)):
            return c
    raise WebusbMockError(
        f"no transferOut on endpoint {endpoint} contained {needle}"
    )


def assert_control_out(
    calls: Iterable[OutgoingCall],
    *, request: int | None = None,
) -> OutgoingCall:
    matches = [c for c in calls if c.kind == "controlOut"]
    if not matches:
        raise WebusbMockError("no controlTransferOut calls")
    if request is None:
        return matches[0]
    for c in matches:
        setup = c.setup if isinstance(c.setup, dict) else {}
        if setup.get("request") == request:
            return c
    raise WebusbMockError(
        f"no controlTransferOut with request={request}"
    )
