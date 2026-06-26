"""
Token-by-token streaming chat assertions.

Modern chat UIs render LLM output as a stream of small deltas (SSE
data lines, websocket text frames, or fetch ReadableStream chunks).
Tests need to confirm:

* Time-to-first-token (TTFT) is acceptable for UX (Apple HIG: < 1s).
* Inter-token gaps don't stall (no > 3s pause that looks like crash).
* Final concatenated text matches an expected pattern.
* Stream eventually closes cleanly (no truncated UTF-8 sequence).
* No duplicate delta or out-of-order chunk arrived (common LB bug).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class StreamingChatAssertError(WebRunnerException):
    """Raised on stream protocol violation or budget bust."""


@dataclass
class TokenDelta:
    """One delta from the stream."""

    text: str = ""
    ts_ms: float = 0
    seq: int | None = None    # if provider numbers chunks

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise StreamingChatAssertError("delta.text must be string")
        if self.ts_ms < 0:
            raise StreamingChatAssertError("ts_ms must be >= 0")


def parse_deltas(payload: Any) -> list[TokenDelta]:
    if not isinstance(payload, list):
        raise StreamingChatAssertError("payload must be a list")
    out: list[TokenDelta] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        out.append(TokenDelta(
            text=str(raw.get("text") or ""),
            ts_ms=float(raw.get("ts_ms") or 0),
            seq=raw.get("seq"),
        ))
    return out


def assemble(deltas: Sequence[TokenDelta]) -> str:
    return "".join(d.text for d in deltas)


def time_to_first_token(deltas: Sequence[TokenDelta]) -> float:
    """Milliseconds from t=0 to the first non-empty delta."""
    for d in deltas:
        if d.text:
            return d.ts_ms
    raise StreamingChatAssertError("no non-empty delta in stream")


def max_inter_token_gap_ms(deltas: Sequence[TokenDelta]) -> float:
    text_deltas = [d for d in deltas if d.text]
    if len(text_deltas) < 2:
        return 0.0
    return max(b.ts_ms - a.ts_ms
               for a, b in zip(text_deltas, text_deltas[1:], strict=False))


def assert_ttft_under(deltas: Sequence[TokenDelta], *, max_ms: float) -> None:
    if max_ms <= 0:
        raise StreamingChatAssertError("max_ms must be positive")
    ttft = time_to_first_token(deltas)
    if ttft > max_ms:
        raise StreamingChatAssertError(
            f"TTFT {ttft:.0f}ms > budget {max_ms:.0f}ms"
        )


def assert_no_stall(deltas: Sequence[TokenDelta], *, max_gap_ms: float) -> None:
    if max_gap_ms <= 0:
        raise StreamingChatAssertError("max_gap_ms must be positive")
    gap = max_inter_token_gap_ms(deltas)
    if gap > max_gap_ms:
        raise StreamingChatAssertError(
            f"max inter-token gap {gap:.0f}ms > {max_gap_ms:.0f}ms"
        )


def assert_assembled_contains(
    deltas: Sequence[TokenDelta], *, expected: str,
) -> None:
    if not expected:
        raise StreamingChatAssertError("expected must be non-empty")
    text = assemble(deltas)
    if expected not in text:
        raise StreamingChatAssertError(
            f"assembled stream missing {expected!r} (got {text[:80]!r}...)"
        )


def assert_utf8_clean(deltas: Sequence[TokenDelta]) -> None:
    """A clean stream must round-trip as UTF-8 with no replacement chars."""
    text = assemble(deltas)
    if "�" in text:
        raise StreamingChatAssertError(
            "assembled stream contains U+FFFD — likely truncated UTF-8 boundary"
        )


def assert_no_dup_or_oos(deltas: Sequence[TokenDelta]) -> None:
    """If the provider numbers chunks (``seq``), they must be strictly
    increasing without duplicates."""
    seen = set()
    prev = -1
    for d in deltas:
        if d.seq is None:
            continue
        if d.seq in seen:
            raise StreamingChatAssertError(f"duplicate chunk seq={d.seq}")
        if d.seq <= prev:
            raise StreamingChatAssertError(
                f"out-of-order chunk seq={d.seq} after {prev}"
            )
        seen.add(d.seq)
        prev = d.seq
