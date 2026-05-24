"""
gRPC / gRPC-Web client harness with request/response capture for E2E
integration testing.
Two paths:

* **Real gRPC** — wraps an injectable ``grpc`` channel; you provide the
  service stub (generated from .proto) and we record every call.
* **gRPC-Web** — pure-HTTP using ``requests``: build a length-prefixed
  payload, decode the trailer. Useful when the SUT is a browser-style
  client; doesn't need protoc generation for raw byte tests.

Both expose the same :class:`GrpcCall` recorder + asserts so suites are
transport-portable.
"""
from __future__ import annotations

import base64
import struct
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException


class GrpcTesterError(WebRunnerException):
    """Raised on malformed input / call failure / failed assertion."""


# ---------- model ------------------------------------------------------

class GrpcStatus(int, Enum):
    """Standard gRPC status codes."""

    OK = 0
    CANCELLED = 1
    UNKNOWN = 2
    INVALID_ARGUMENT = 3
    DEADLINE_EXCEEDED = 4
    NOT_FOUND = 5
    ALREADY_EXISTS = 6
    PERMISSION_DENIED = 7
    UNAUTHENTICATED = 16


@dataclass
class GrpcCall:
    """One recorded gRPC / gRPC-Web call."""

    method: str
    request: Any
    response: Any
    status: GrpcStatus
    duration_ms: float
    metadata: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "status": self.status.name}


# ---------- recorder ----------------------------------------------------

class GrpcCallRecorder:
    """In-memory recorder of calls."""

    def __init__(self) -> None:
        self._calls: List[GrpcCall] = []

    def __len__(self) -> int:
        return len(self._calls)

    def record(self, call: GrpcCall) -> None:
        if not isinstance(call, GrpcCall):
            raise GrpcTesterError(
                f"record() expects GrpcCall, got {type(call).__name__}"
            )
        self._calls.append(call)

    def clear(self) -> None:
        self._calls.clear()

    def calls(
        self,
        *,
        method: Optional[str] = None,
        status: Optional[GrpcStatus] = None,
    ) -> List[GrpcCall]:
        out: List[GrpcCall] = []
        for c in self._calls:
            if method is not None and c.method != method:
                continue
            if status is not None and c.status != status:
                continue
            out.append(c)
        return out


# ---------- callable wrapper ------------------------------------------

def call(
    method: str,
    stub_method: Callable[..., Any],
    request: Any,
    *,
    recorder: Optional[GrpcCallRecorder] = None,
    metadata: Optional[Sequence[Tuple[str, str]]] = None,
    timeout: Optional[float] = None,
) -> GrpcCall:
    """
    Call a generated gRPC stub method, capturing response / status.
    Returns the :class:`GrpcCall` whether the call succeeded or raised.
    """
    if not isinstance(method, str) or not method:
        raise GrpcTesterError("method must be non-empty string")
    if not callable(stub_method):
        raise GrpcTesterError("stub_method must be callable")
    metadata = list(metadata or [])
    started = time.monotonic()
    status = GrpcStatus.OK
    response = None
    error: Optional[str] = None
    try:
        kwargs: Dict[str, Any] = {}
        if metadata:
            kwargs["metadata"] = metadata
        if timeout is not None:
            kwargs["timeout"] = timeout
        response = stub_method(request, **kwargs)
    except Exception as exc:
        # Try to read .code() like grpc.RpcError; fall back to UNKNOWN.
        code_obj = getattr(exc, "code", None)
        code_val = code_obj() if callable(code_obj) else code_obj
        status = _coerce_status(code_val)
        error = repr(exc)
    duration = round((time.monotonic() - started) * 1000.0, 3)
    record = GrpcCall(
        method=method, request=request, response=response,
        status=status, duration_ms=duration,
        metadata=dict(metadata), error=error,
    )
    if recorder is not None:
        recorder.record(record)
    return record


def _coerce_status(value: Any) -> GrpcStatus:
    if value is None:
        return GrpcStatus.UNKNOWN
    if isinstance(value, GrpcStatus):
        return value
    if isinstance(value, int):
        try:
            return GrpcStatus(value)
        except ValueError:
            return GrpcStatus.UNKNOWN
    # grpc.StatusCode has a .value tuple (int, str)
    code = getattr(value, "value", None)
    if isinstance(code, tuple) and code and isinstance(code[0], int):
        try:
            return GrpcStatus(code[0])
        except ValueError:
            return GrpcStatus.UNKNOWN
    return GrpcStatus.UNKNOWN


# ---------- gRPC-Web framing ------------------------------------------

def encode_grpc_web_message(payload: bytes) -> bytes:
    """Length-prefix-frame a raw payload (compression flag 0)."""
    if not isinstance(payload, (bytes, bytearray)):
        raise GrpcTesterError("payload must be bytes")
    return b"\x00" + struct.pack(">I", len(payload)) + bytes(payload)


def decode_grpc_web_message(framed: bytes) -> List[Tuple[int, bytes]]:
    """Decode a (possibly multi-message) framed gRPC-Web body."""
    if not isinstance(framed, (bytes, bytearray)):
        raise GrpcTesterError("framed must be bytes")
    out: List[Tuple[int, bytes]] = []
    pos = 0
    buf = bytes(framed)
    while pos < len(buf):
        if len(buf) - pos < 5:
            raise GrpcTesterError(f"truncated frame at offset {pos}")
        flag = buf[pos]
        length = struct.unpack(">I", buf[pos + 1:pos + 5])[0]
        end = pos + 5 + length
        if end > len(buf):
            raise GrpcTesterError(f"frame length overruns buffer at {pos}")
        out.append((flag, buf[pos + 5:end]))
        pos = end
    return out


def parse_trailer(trailer_bytes: bytes) -> Dict[str, str]:
    """Parse a ``grpc-status`` / ``grpc-message`` trailer payload."""
    if not isinstance(trailer_bytes, (bytes, bytearray)):
        raise GrpcTesterError("trailer_bytes must be bytes")
    text = bytes(trailer_bytes).decode("utf-8", errors="replace")
    out: Dict[str, str] = {}
    for line in text.split("\r\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        name, _, value = line.partition(":")
        out[name.strip().lower()] = value.strip()
    return out


# ---------- assertions -------------------------------------------------

def assert_call_ok(call_record: GrpcCall) -> None:
    """Assert ``call_record.status == OK``."""
    if not isinstance(call_record, GrpcCall):
        raise GrpcTesterError("expects GrpcCall")
    if call_record.status != GrpcStatus.OK:
        raise GrpcTesterError(
            f"call {call_record.method!r} returned {call_record.status.name}: "
            f"{call_record.error or 'no error message'}"
        )


def assert_call_fails(call_record: GrpcCall, *, status: GrpcStatus) -> None:
    """Assert a specific non-OK status."""
    if not isinstance(call_record, GrpcCall):
        raise GrpcTesterError("expects GrpcCall")
    if not isinstance(status, GrpcStatus):
        raise GrpcTesterError("status must be GrpcStatus")
    if call_record.status != status:
        raise GrpcTesterError(
            f"expected {status.name}, got {call_record.status.name}"
        )


def assert_called(
    recorder: GrpcCallRecorder,
    method: str,
    *,
    minimum: int = 1,
) -> int:
    """Assert a method was invoked at least ``minimum`` times."""
    count = len(recorder.calls(method=method))
    if count < minimum:
        raise GrpcTesterError(
            f"method {method!r} called {count} times, want >= {minimum}"
        )
    return count
