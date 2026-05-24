"""
Embedding-based action JSON 語意去重。
"我們有 50 個 test 都在測登入" — `test_dedup_ai` 抓出來。Two levels:

* **Structural dedupe** — exact-match canonicalised action sequences
  catch literal copy-paste; pure stdlib, no model required.
* **Semantic dedupe** — caller-supplied :class:`Embedder` provides
  embeddings; we cluster by cosine similarity. The embedder is a simple
  callable so tests can plug in a stub vector, and production code can
  use OpenAI / Voyage / a local model.

Both modes share the same clustering output, so downstream tooling treats
them uniformly.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException


class TestDedupError(WebRunnerException):
    """Raised on malformed action files, bad embeddings, or bad config."""


# ---------- canonicalisation -------------------------------------------

def _canonicalise(actions: Sequence[Dict[str, Any]]) -> str:
    """
    Reduce an action list to a structure-only fingerprint.
    Drops user-data (URL paths, typed text) so two tests that differ only
    in test-data end up with the same fingerprint.
    """
    if not isinstance(actions, list):
        raise TestDedupError("actions must be a list")
    pieces: List[str] = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or len(action) != 1:
            raise TestDedupError(
                f"action #{index} must be a single-key dict, got {action!r}"
            )
        name, args = next(iter(action.items()))
        if not isinstance(args, list):
            raise TestDedupError(
                f"action #{index} ({name}) args must be a list"
            )
        kind_sig = _arg_type_signature(args)
        pieces.append(f"{name}({kind_sig})")
    return " > ".join(pieces)


def _arg_type_signature(args: List[Any]) -> str:
    parts: List[str] = []
    for arg in args:
        if isinstance(arg, bool):
            parts.append("bool")
        elif isinstance(arg, (int, float)):
            parts.append("number")
        elif isinstance(arg, str):
            parts.append(f"str[{_string_kind(arg)}]")
        elif isinstance(arg, list):
            parts.append("list")
        elif isinstance(arg, dict):
            parts.append("dict")
        else:
            parts.append(type(arg).__name__)
    return ",".join(parts)


def _string_kind(value: str) -> str:
    """Crude bucket: 'locator' / 'url' / 'short' / 'long' so canonical."""
    if value.startswith(("http://", "https://")):
        return "url"
    if value in {"id", "name", "xpath", "link text", "partial link text",
                 "tag name", "class name", "css selector"}:
        return "by"
    if len(value) <= 12:
        return "short"
    return "long"


# ---------- file loading -----------------------------------------------

@dataclass
class ActionFile:
    """One on-disk action JSON file."""

    path: str
    actions: List[Dict[str, Any]]
    fingerprint: str = ""

    @classmethod
    def load(cls, path: Union[str, Path]) -> "ActionFile":
        p = Path(path)
        if not p.exists():
            raise TestDedupError(f"action file not found: {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as error:
            raise TestDedupError(f"action file {p} is not JSON: {error}") from error
        if not isinstance(data, list):
            raise TestDedupError(f"action file {p} must contain a JSON list")
        instance = cls(path=str(p), actions=data)
        instance.fingerprint = _canonicalise(data)
        return instance


def load_dir(directory: Union[str, Path]) -> List[ActionFile]:
    """Load every ``*.json`` file in ``directory`` (non-recursive)."""
    d = Path(directory)
    if not d.is_dir():
        raise TestDedupError(f"not a directory: {d}")
    return [ActionFile.load(child) for child in sorted(d.glob("*.json"))]


# ---------- cluster model ----------------------------------------------

@dataclass
class DuplicateCluster:
    """A set of files judged equivalent under the chosen mode."""

    mode: str  # 'structural' | 'semantic'
    members: List[str] = field(default_factory=list)
    representative: str = ""
    similarity_threshold: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------- structural dedupe -------------------------------------------

def structural_clusters(files: Sequence[ActionFile]) -> List[DuplicateCluster]:
    """Group by canonical fingerprint. Singletons are dropped."""
    if not files:
        raise TestDedupError("files must be a non-empty sequence")
    buckets: Dict[str, List[str]] = {}
    for f in files:
        buckets.setdefault(f.fingerprint, []).append(f.path)
    clusters: List[DuplicateCluster] = []
    for fingerprint, paths in buckets.items():
        if len(paths) <= 1:
            continue
        clusters.append(DuplicateCluster(
            mode="structural",
            members=sorted(paths),
            representative=sorted(paths)[0],
            similarity_threshold=1.0,
        ))
    clusters.sort(key=lambda c: -len(c.members))
    return clusters


# ---------- semantic dedupe --------------------------------------------

Embedder = Callable[[str], Sequence[float]]
"""Callable: text → embedding vector."""


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        raise TestDedupError("embeddings must be non-empty and equal-length")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _summary_for(file: ActionFile) -> str:
    """Compact text representation an embedder will encode."""
    parts: List[str] = []
    for action in file.actions[:25]:  # cap to keep embeddings stable
        if not isinstance(action, dict) or len(action) != 1:
            continue
        name, args = next(iter(action.items()))
        textual = [str(a) for a in args if isinstance(a, str)][:3]
        if textual:
            parts.append(f"{name}: {' '.join(textual)}")
        else:
            parts.append(name)
    return " | ".join(parts)


def semantic_clusters(
    files: Sequence[ActionFile],
    embedder: Embedder,
    *,
    similarity_threshold: float = 0.92,
) -> List[DuplicateCluster]:
    """
    Group files whose summary embeddings are pairwise above
    ``similarity_threshold``. Uses simple agglomerative union-find; fine
    for the test-suite scale (hundreds, not millions).
    """
    if not files:
        raise TestDedupError("files must be a non-empty sequence")
    if not 0.0 < similarity_threshold <= 1.0:
        raise TestDedupError("similarity_threshold must be in (0, 1]")
    embeddings: List[Sequence[float]] = []
    for f in files:
        try:
            vector = embedder(_summary_for(f))
        except Exception as error:
            raise TestDedupError(
                f"embedder failed for {f.path}: {error!r}"
            ) from error
        if not isinstance(vector, (list, tuple)) or not vector:
            raise TestDedupError(
                f"embedder returned bad vector for {f.path}: {vector!r}"
            )
        embeddings.append(list(vector))
    parent = list(range(len(files)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        a, b = find(i), find(j)
        if a != b:
            parent[a] = b

    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            if _cosine(embeddings[i], embeddings[j]) >= similarity_threshold:
                union(i, j)

    groups: Dict[int, List[int]] = {}
    for i in range(len(files)):
        groups.setdefault(find(i), []).append(i)

    clusters: List[DuplicateCluster] = []
    for indices in groups.values():
        if len(indices) <= 1:
            continue
        paths = sorted(files[i].path for i in indices)
        clusters.append(DuplicateCluster(
            mode="semantic",
            members=paths,
            representative=paths[0],
            similarity_threshold=similarity_threshold,
        ))
    clusters.sort(key=lambda c: -len(c.members))
    return clusters


# ---------- reporting --------------------------------------------------

def clusters_markdown(clusters: Sequence[DuplicateCluster]) -> str:
    """Render a small markdown table of duplicate clusters."""
    if not clusters:
        return "_No duplicate test clusters found._\n"
    lines = [
        "| Mode | Members | Representative | Threshold |",
        "|------|---------|----------------|-----------|",
    ]
    for c in clusters:
        members = ", ".join(f"`{m}`" for m in c.members[:6])
        if len(c.members) > 6:
            members += f" (+{len(c.members) - 6} more)"
        lines.append(
            f"| {c.mode} | {members} | `{c.representative}` | {c.similarity_threshold:.2f} |"
        )
    return "\n".join(lines) + "\n"


def stable_fingerprint(actions: Sequence[Dict[str, Any]]) -> str:
    """SHA-256 of the canonical fingerprint. Stable across processes."""
    raw = _canonicalise(actions)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
