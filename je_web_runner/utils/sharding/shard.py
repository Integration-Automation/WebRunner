"""
Test sharding：把檔案清單依 hash 分成 N 份，跨機平行跑。
Deterministic test sharding. Splits a list of file paths into ``total``
buckets keyed by a stable hash so each runner picks the same files for the
same shard index across machines.
"""
from __future__ import annotations

import hashlib
from typing import List, Sequence, Tuple

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class ShardingError(WebRunnerException):
    """Raised when a shard spec is invalid."""


def parse_shard_spec(spec: str) -> Tuple[int, int]:
    """
    把 ``"1/4"`` 解析為 ``(1, 4)``
    Parse the ``index/total`` form. Both numbers are positive integers and
    ``index <= total``.
    """
    if not isinstance(spec, str) or "/" not in spec:
        raise ShardingError(f"shard spec must be 'index/total', got {spec!r}")
    left, right = spec.split("/", 1)
    try:
        index = int(left.strip())
        total = int(right.strip())
    except ValueError as error:
        raise ShardingError(f"shard spec must contain integers: {spec!r}") from error
    if total <= 0:
        raise ShardingError("shard total must be > 0")
    if index <= 0 or index > total:
        raise ShardingError(f"shard index {index} out of range 1..{total}")
    return index, total


def _bucket(path: str, total: int) -> int:
    # File partitioning, not crypto — SHA-1 is fine here. NOSONAR
    # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
    digest = hashlib.sha1(path.encode("utf-8"), usedforsecurity=False).hexdigest()  # nosec B324
    return int(digest, 16) % total


def partition(paths: Sequence[str], index: int, total: int) -> List[str]:
    """
    回傳該 shard 應該執行的檔案路徑（依檔名 SHA-1 對 ``total`` 取模）
    Return the subset of ``paths`` that belongs to shard ``index`` (1-based)
    out of ``total`` shards. Hashing the path means each runner picks the
    same files without coordination.
    """
    if total <= 0:
        raise ShardingError("total must be > 0")
    if index <= 0 or index > total:
        raise ShardingError(f"index {index} out of range 1..{total}")
    selected = [path for path in paths if _bucket(str(path), total) == index - 1]
    web_runner_logger.info(
        f"shard {index}/{total} picked {len(selected)} of {len(paths)} files"
    )
    return selected


def partition_with_spec(paths: Sequence[str], spec: str) -> List[str]:
    """Convenience: parse the spec then partition."""
    index, total = parse_shard_spec(spec)
    return partition(paths, index, total)
