"""
Payment Request API + Apple Pay / Google Pay sheet assertions.

Real payment sheets can't be driven by Selenium / Playwright (they're
out-of-process browser UI). This module installs a JS shim that:

* Replaces ``window.PaymentRequest`` with a recorder that captures the
  payment methods array, payment details, and shipping options the page
  passed to the constructor.
* Returns a canned ``PaymentResponse`` so the page's ``show()`` flow
  can complete without user interaction.
* Records the ``complete()`` call (and its status) so tests can confirm
  the page actually finalized the transaction.

Python-side assertions cover the common contract failures (missing
Apple Pay capability, total mismatched currency, no shipping option).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class PaymentRequestAssertError(WebRunnerException):
    """Raised on malformed input or assertion failure."""


INSTALL_SCRIPT = r"""
(function (canned) {
  if (window.__wr_payment__) return;
  const constructed = [];
  const completed = [];
  function FakePaymentRequest(methodData, details, options) {
    constructed.push({methodData, details, options});
    this._methodData = methodData;
    this._details = details;
    this._options = options;
  }
  FakePaymentRequest.prototype.show = async function () {
    return {
      requestId: canned.requestId || 'wr-pr-1',
      methodName: canned.methodName ||
        (this._methodData[0] && this._methodData[0].supportedMethods) ||
        'basic-card',
      details: canned.details || {token: 'wr-token'},
      shippingAddress: canned.shippingAddress || null,
      shippingOption: canned.shippingOption || null,
      payerEmail: canned.payerEmail || null,
      payerName: canned.payerName || null,
      payerPhone: canned.payerPhone || null,
      complete: async function (status) {
        completed.push({status: status || 'unknown'});
      },
    };
  };
  FakePaymentRequest.prototype.canMakePayment = async function () {
    return canned.canMakePayment !== false;
  };
  FakePaymentRequest.prototype.abort = async function () {};
  window.PaymentRequest = FakePaymentRequest;
  window.__wr_payment__ = {
    drainConstructed: function () { return constructed.splice(0); },
    drainCompleted: function () { return completed.splice(0); },
  };
})(arguments[0]);
"""


@dataclass
class ConstructedPaymentRequest:
    method_data: List[Dict[str, Any]] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)

    def supports_method(self, method: str) -> bool:
        return any((m.get("supportedMethods") or "") == method
                   for m in self.method_data if isinstance(m, dict))


@dataclass
class CompletedPayment:
    status: str = "unknown"


@dataclass
class PaymentLog:
    constructed: List[ConstructedPaymentRequest] = field(default_factory=list)
    completed: List[CompletedPayment] = field(default_factory=list)


def parse_log(payload: Any) -> PaymentLog:
    if not isinstance(payload, dict):
        raise PaymentRequestAssertError("payload must be dict")
    constructed: List[ConstructedPaymentRequest] = []
    for raw in payload.get("constructed") or []:
        if not isinstance(raw, dict):
            continue
        constructed.append(ConstructedPaymentRequest(
            method_data=list(raw.get("methodData") or []),
            details=dict(raw.get("details") or {}),
            options=dict(raw.get("options") or {}),
        ))
    completed: List[CompletedPayment] = []
    for raw in payload.get("completed") or []:
        if not isinstance(raw, dict):
            continue
        completed.append(CompletedPayment(status=str(raw.get("status") or "unknown")))
    return PaymentLog(constructed=constructed, completed=completed)


def assert_supports(log: PaymentLog, *, method: str) -> None:
    if not method:
        raise PaymentRequestAssertError("method must be non-empty")
    if not log.constructed:
        raise PaymentRequestAssertError("page never constructed a PaymentRequest")
    if not any(c.supports_method(method) for c in log.constructed):
        offered = sorted({m.get("supportedMethods", "?")
                          for c in log.constructed for m in c.method_data
                          if isinstance(m, dict)})
        raise PaymentRequestAssertError(
            f"no PaymentRequest declared support for {method!r}; "
            f"offered={offered}"
        )


def assert_total_currency(log: PaymentLog, *, currency: str) -> None:
    if not currency:
        raise PaymentRequestAssertError("currency must be non-empty")
    for c in log.constructed:
        total = c.details.get("total") or {}
        amount = total.get("amount") or {} if isinstance(total, dict) else {}
        if isinstance(amount, dict) and amount.get("currency") != currency:
            raise PaymentRequestAssertError(
                f"total currency {amount.get('currency')!r} != {currency!r}"
            )


def assert_completed(log: PaymentLog, *, status: str = "success") -> None:
    if status not in ("success", "fail", "unknown"):
        raise PaymentRequestAssertError(f"invalid status {status!r}")
    if not log.completed:
        raise PaymentRequestAssertError(
            "page never called PaymentResponse.complete() — "
            "transaction left dangling"
        )
    actual = {c.status for c in log.completed}
    if status not in actual:
        raise PaymentRequestAssertError(
            f"complete() called with statuses {actual}, expected {status!r}"
        )


def assert_shipping_required(log: PaymentLog) -> None:
    for c in log.constructed:
        if not c.options.get("requestShipping"):
            raise PaymentRequestAssertError(
                "PaymentRequest constructed without requestShipping:true"
            )
