"""
Message-queue assertion helpers (Kafka / RabbitMQ / SQS-style).

Verifies that an action triggered by a UI step actually produced the
expected downstream event. The transport is delegated via a ``Consumer``
``Protocol`` so we don't drag in any one client library — callers supply
a simple ``drain()`` function that returns a list of ``Message`` records.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class MqAssertError(WebRunnerException):
    """Raised when a message-queue invariant is violated."""


@dataclass
class Message:
    topic: str
    body: Any
    key: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)

    def body_as_dict(self) -> Dict[str, Any]:
        if isinstance(self.body, dict):
            return self.body
        if isinstance(self.body, (bytes, str)):
            try:
                parsed = json.loads(self.body)
            except (ValueError, TypeError) as exc:
                raise MqAssertError(
                    f"message body is not valid JSON: {self.body!r}"
                ) from exc
            if isinstance(parsed, dict):
                return parsed
            raise MqAssertError("decoded JSON is not an object")
        raise MqAssertError(f"unsupported body type: {type(self.body).__name__}")


class Consumer(Protocol):
    def drain(self, topic: str, *, timeout: float = 5.0) -> Sequence[Message]: ...


def drain_topic(
    consumer: Consumer, topic: str, timeout: float = 5.0,
) -> List[Message]:
    if not topic:
        raise MqAssertError("topic must be non-empty")
    if not hasattr(consumer, "drain"):
        raise MqAssertError("consumer must implement drain(topic, timeout=)")
    raw = consumer.drain(topic, timeout=timeout)
    if not isinstance(raw, (list, tuple)):
        raise MqAssertError("consumer.drain must return a sequence")
    out: List[Message] = []
    for m in raw:
        if isinstance(m, Message):
            out.append(m)
        elif isinstance(m, dict):
            out.append(Message(
                topic=str(m.get("topic") or topic),
                body=m.get("body"),
                key=m.get("key"),
                headers=dict(m.get("headers") or {}),
            ))
        else:
            raise MqAssertError(
                f"unsupported message shape: {type(m).__name__}"
            )
    return out


def _matches(message: Message, *,
             body_contains: Optional[Dict[str, Any]] = None,
             key_matches: Optional[str] = None,
             header_equals: Optional[Dict[str, str]] = None) -> bool:
    if key_matches is not None and message.key != key_matches:
        return False
    if header_equals:
        for k, v in header_equals.items():
            if message.headers.get(k) != v:
                return False
    if body_contains:
        try:
            body = message.body_as_dict()
        except MqAssertError:
            return False
        for k, v in body_contains.items():
            if body.get(k) != v:
                return False
    return True


def assert_message_published(
    messages: Sequence[Message],
    *,
    body_contains: Optional[Dict[str, Any]] = None,
    key_matches: Optional[str] = None,
    header_equals: Optional[Dict[str, str]] = None,
) -> Message:
    """Find one matching message or raise."""
    if not isinstance(messages, (list, tuple)):
        raise MqAssertError("messages must be a sequence")
    for m in messages:
        if _matches(m, body_contains=body_contains,
                    key_matches=key_matches, header_equals=header_equals):
            return m
    raise MqAssertError(
        "no matching message; "
        f"body_contains={body_contains!r}, "
        f"key={key_matches!r}, headers={header_equals!r}"
    )


def assert_no_message(
    messages: Sequence[Message],
    *,
    topic: Optional[str] = None,
    body_contains: Optional[Dict[str, Any]] = None,
) -> None:
    """Useful for `should NOT have published anything sensitive`."""
    for m in messages:
        if topic is not None and m.topic != topic:
            continue
        if _matches(m, body_contains=body_contains):
            raise MqAssertError(
                f"unexpected message published on {m.topic}: {m.body!r}"
            )


def assert_idempotent(messages: Sequence[Message], *, key: str) -> None:
    """For idempotency keys: at most one message per key."""
    matching = [m for m in messages if m.key == key]
    if len(matching) > 1:
        raise MqAssertError(
            f"duplicate publish for key {key!r}: count={len(matching)}"
        )


def assert_ordered(
    messages: Sequence[Message], *, key: str, expected_order: Sequence[str],
) -> None:
    """Confirm same-key messages arrived in the expected ``type`` order."""
    relevant = [m for m in messages if m.key == key]
    actual = []
    for m in relevant:
        try:
            actual.append(m.body_as_dict().get("type"))
        except MqAssertError:
            actual.append(None)
    if actual != list(expected_order):
        raise MqAssertError(
            f"order mismatch for key {key!r}: "
            f"expected {list(expected_order)}, got {actual}"
        )
