"""
WebHID mock — install a navigator.hid shim in the page so tests can
simulate a Human Interface Device without real hardware.

The harness ships:

* ``INSTALL_SCRIPT`` — a JS snippet that monkey-patches ``navigator.hid``
  with a fake device queue and exposes ``window.__wr_hid__`` for the test
  driver to push input reports / capture output reports.
* Python helpers to ``build_mock_device``, ``build_input_report`` (one row
  of bytes), and the assertion ``assert_output_reports`` to validate what
  the page sent back to the "device".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebhidMockError(WebRunnerException):
    """Raised when input is malformed or assertions fail."""


INSTALL_SCRIPT = r"""
(function (devices) {
  if (window.__wr_hid__) return;
  const incoming = [];   // pending input reports queued from test
  const outgoing = [];   // output reports the page wrote
  const listeners = new WeakMap();
  function FakeDevice(spec) {
    this.vendorId = spec.vendor_id;
    this.productId = spec.product_id;
    this.productName = spec.product_name;
    this.opened = false;
  }
  FakeDevice.prototype.open = async function () { this.opened = true; };
  FakeDevice.prototype.close = async function () { this.opened = false; };
  FakeDevice.prototype.addEventListener = function (e, cb) {
    if (!listeners.has(this)) listeners.set(this, []);
    listeners.get(this).push(cb);
  };
  FakeDevice.prototype.sendReport = async function (id, bytes) {
    outgoing.push({reportId: id, data: Array.from(new Uint8Array(bytes))});
  };
  const fakeDevices = devices.map((d) => new FakeDevice(d));
  navigator.hid = {
    requestDevice: async () => fakeDevices,
    getDevices: async () => fakeDevices,
    addEventListener: () => {},
  };
  window.__wr_hid__ = {
    pushReport: function (deviceIndex, reportId, bytes) {
      const dev = fakeDevices[deviceIndex];
      if (!dev || !dev.opened) return false;
      const cbs = listeners.get(dev) || [];
      const ev = {device: dev, reportId, data: new DataView(
        new Uint8Array(bytes).buffer)};
      cbs.forEach((cb) => cb(ev));
      return true;
    },
    drainOutgoing: function () { return outgoing.splice(0); },
    listDevices: function () { return fakeDevices.map((d) => ({
      vendorId: d.vendorId, productId: d.productId,
      productName: d.productName, opened: d.opened,
    })); },
  };
})(arguments[0]);
"""


@dataclass
class MockDevice:
    vendor_id: int
    product_id: int
    product_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "product_name": self.product_name,
        }


def build_mock_device(
    vendor_id: int, product_id: int, product_name: str = "",
) -> MockDevice:
    if not 0 <= vendor_id <= 0xFFFF or not 0 <= product_id <= 0xFFFF:
        raise WebhidMockError("vendor/product id must fit in uint16")
    return MockDevice(vendor_id=vendor_id, product_id=product_id,
                      product_name=product_name)


def build_input_report(report_id: int, data: Sequence[int]) -> dict[str, Any]:
    if not 0 <= report_id <= 255:
        raise WebhidMockError("report_id must be 0..255")
    if not isinstance(data, (list, tuple)):
        raise WebhidMockError("data must be a sequence of ints")
    if any(not isinstance(b, int) or not 0 <= b <= 255 for b in data):
        raise WebhidMockError("data must be ints in 0..255")
    return {"report_id": report_id, "data": list(data)}


@dataclass
class OutgoingReport:
    report_id: int
    data: list[int] = field(default_factory=list)


def _outgoing_report_id(raw: dict[str, Any]) -> int:
    """Read the report id from either key; report id ``0`` is valid (single-
    report devices), so a falsy-coalesce would wrongly discard it."""
    value = raw.get("reportId")
    if value is None:
        value = raw.get("report_id")
    return int(value) if value is not None else 0


def parse_outgoing(payload: Any) -> list[OutgoingReport]:
    if not isinstance(payload, list):
        raise WebhidMockError("payload must be a list")
    out: list[OutgoingReport] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        out.append(OutgoingReport(
            report_id=_outgoing_report_id(raw),
            data=[int(b) for b in (raw.get("data") or [])],
        ))
    return out


def assert_output_reports(
    reports: Iterable[OutgoingReport],
    *, expected_count: int | None = None,
    contains: Sequence[int] | None = None,
) -> None:
    rs = list(reports)
    if expected_count is not None and len(rs) != expected_count:
        raise WebhidMockError(
            f"expected {expected_count} outgoing reports, got {len(rs)}"
        )
    if contains is not None:
        needle = list(contains)
        for r in rs:
            if any(r.data[i:i + len(needle)] == needle
                   for i in range(len(r.data) - len(needle) + 1)):
                return
        raise WebhidMockError(
            f"none of the outgoing reports contained {needle}"
        )
