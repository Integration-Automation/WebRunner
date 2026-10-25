"""Neutral host-owned identity and monotonic read-only state for one managed context."""
from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any, Literal
import uuid


@dataclass
class ManagedContextState:
    """Keep context anchors private; a serialized description never grants access."""

    context_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    mode: Literal["writable", "freezing", "readonly"] = "writable"
    anchor: tuple[Any, Any, str] | None = None
    view: Any = None
    active: int = 0
    owner_thread: threading.Thread = field(default_factory=threading.current_thread)
