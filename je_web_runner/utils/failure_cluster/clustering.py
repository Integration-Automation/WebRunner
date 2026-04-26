"""
失敗分群：把多次跑的失敗依 normalised error signature 分群，列出 top buckets。
Failure clustering. Each failure record (``{function_name, exception,
file_path?}``) is reduced to a stable signature by stripping volatile
substrings (timestamps, hex addresses, line numbers, file paths,
arbitrary numbers) so the same root cause across runs lands in one
bucket.

The signature is intentionally aggressive — false grouping is preferable
to a long-tail of singleton clusters during triage.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class FailureClusterError(WebRunnerException):
    """Raised when the failures iterable has the wrong shape."""


@dataclass
class FailureCluster:
    """One bucket of failures sharing a normalised signature."""

    signature: str
    representative: str
    count: int = 0
    members: List[Dict[str, Any]] = field(default_factory=list)
    files: List[str] = field(default_factory=list)


_HEX_ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]+")
_LINE_NO_RE = re.compile(r"line\s+\d+", re.IGNORECASE)
# The timestamp regex was flagged by SonarCloud S5843 for cognitive
# complexity; split the date / time / fraction / zone parts so each
# piece stays simple.
_TIMESTAMP_DATE = r"\d{4}-\d{2}-\d{2}"
_TIMESTAMP_TIME = r"\d{2}:\d{2}:\d{2}"
_TIMESTAMP_FRACTION = r"(?:\.\d+)?"
_TIMESTAMP_ZONE = r"(?:Z|[+-]\d{2}:?\d{2})?"
_TIMESTAMP_RE = re.compile(
    _TIMESTAMP_DATE + r"[T ]" + _TIMESTAMP_TIME + _TIMESTAMP_FRACTION + _TIMESTAMP_ZONE
)
# Bounded character class size + finite outer repetition keeps backtracking
# bounded; Semgrep's heuristic still flags the pattern because of the nested
# quantifiers, but the worst case is O(80*40*input) which is linear-ish for
# realistic error messages. NOSONAR S5852.
# nosemgrep: python.lang.security.audit.regex-dos.regex_dos
_PATH_RE = re.compile(
    r"(?:[A-Za-z]:)?[\\/](?:[\w.\-]{1,80}[\\/]){1,40}[\w.\-]{1,80}"
)
_NUMBER_RE = re.compile(r"\b\d{2,}\b")
_QUOTED_RE = re.compile(r"'[^']{0,80}'|\"[^\"]{0,80}\"")
_WHITESPACE_RE = re.compile(r"\s+")


def normalise_error(message: str) -> str:
    """
    把錯誤訊息做積極正規化，方便後續分群比較。
    Strip timestamps, hex addresses, file paths, line numbers, large
    numerics, and quoted substrings. Returns a lower-cased canonical form.
    """
    if not isinstance(message, str):
        return ""
    text = message
    text = _TIMESTAMP_RE.sub("<TS>", text)
    text = _HEX_ADDRESS_RE.sub("<HEX>", text)
    text = _LINE_NO_RE.sub("line <N>", text)
    text = _PATH_RE.sub("<PATH>", text)
    text = _NUMBER_RE.sub("<N>", text)
    text = _QUOTED_RE.sub("<Q>", text)
    text = _WHITESPACE_RE.sub(" ", text).strip().lower()
    return text


def cluster_failures(
    failures: Iterable[Dict[str, Any]],
    top_n: Optional[int] = None,
) -> List[FailureCluster]:
    """
    把 ``[{function_name, exception, file_path?}, …]`` 分群並依 count 排序。
    Group failures by normalised signature; clusters are sorted by count
    descending. ``top_n`` truncates the result to the largest buckets.
    """
    if failures is None:
        raise FailureClusterError("failures must be iterable")
    buckets: Dict[str, FailureCluster] = {}
    for failure in failures:
        if not isinstance(failure, dict):
            raise FailureClusterError(
                f"failure entries must be dicts, got {type(failure).__name__}"
            )
        message = str(failure.get("exception") or failure.get("error") or "")
        signature = normalise_error(message)
        if not signature:
            signature = "<unknown>"
        bucket = buckets.get(signature)
        if bucket is None:
            bucket = FailureCluster(
                signature=signature,
                representative=message[:200],
            )
            buckets[signature] = bucket
        bucket.count += 1
        bucket.members.append(failure)
        file_path = failure.get("file_path")
        if isinstance(file_path, str) and file_path and file_path not in bucket.files:
            bucket.files.append(file_path)
    ordered = sorted(buckets.values(), key=lambda c: (-c.count, c.signature))
    if top_n is not None:
        ordered = ordered[:max(0, top_n)]
    return ordered


def cluster_summary(clusters: Iterable[FailureCluster]) -> List[Dict[str, Any]]:
    """Project clusters to ``{signature, count, files, representative}`` dicts."""
    return [
        {
            "signature": c.signature,
            "count": c.count,
            "representative": c.representative,
            "files": list(c.files),
        }
        for c in clusters
    ]
