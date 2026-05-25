"""
CompressionStream / DecompressionStream round-trip verification.

This module lets a Python test confirm that data the page compresses
with the Compression Streams API can be decompressed by the standard
``gzip`` / ``zlib`` / ``brotli`` libs (and vice versa). Helps catch:

* Wrong algorithm constant (``deflate-raw`` vs ``deflate``).
* Encoding stripped before transit (page calls ``.text()`` instead of
  ``.arrayBuffer()``).
* Brotli used where a CDN strips ``br`` Content-Encoding.
"""
from __future__ import annotations

import gzip
import io
import zlib
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException


class CompressionStreamsError(WebRunnerException):
    """Raised when a round-trip check fails or input is malformed."""


class Algorithm(str, Enum):
    GZIP = "gzip"
    DEFLATE = "deflate"
    DEFLATE_RAW = "deflate-raw"
    BROTLI = "br"


HARVEST_SCRIPT = r"""
async (algorithm, text) => {
  const stream = new Blob([text]).stream();
  const compressed = stream.pipeThrough(new CompressionStream(algorithm));
  const chunks = [];
  const reader = compressed.getReader();
  while (true) {
    const {value, done} = await reader.read();
    if (done) break;
    chunks.push(value);
  }
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const merged = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) { merged.set(c, off); off += c.length; }
  let bin = '';
  for (const b of merged) bin += String.fromCharCode(b);
  return btoa(bin);
};
"""


def decompress(data: bytes, algorithm: Algorithm) -> bytes:
    if not isinstance(data, (bytes, bytearray)):
        raise CompressionStreamsError("data must be bytes")
    if not isinstance(algorithm, Algorithm):
        raise CompressionStreamsError(
            "algorithm must be Algorithm enum"
        )
    if algorithm == Algorithm.GZIP:
        try:
            return gzip.decompress(bytes(data))
        except OSError as exc:
            raise CompressionStreamsError(
                f"gzip decompression failed: {exc!r}"
            ) from exc
    if algorithm == Algorithm.DEFLATE:
        try:
            return zlib.decompress(bytes(data))
        except zlib.error as exc:
            raise CompressionStreamsError(
                f"deflate decompression failed: {exc!r}"
            ) from exc
    if algorithm == Algorithm.DEFLATE_RAW:
        try:
            return zlib.decompress(bytes(data), -zlib.MAX_WBITS)
        except zlib.error as exc:
            raise CompressionStreamsError(
                f"deflate-raw decompression failed: {exc!r}"
            ) from exc
    # brotli is optional
    try:
        import brotli   # type: ignore
    except ImportError as exc:
        raise CompressionStreamsError(
            "brotli decompression requested but `brotli` package not installed"
        ) from exc
    try:
        return brotli.decompress(bytes(data))
    except brotli.error as exc:   # pragma: no cover - depends on optional dep
        raise CompressionStreamsError(
            f"brotli decompression failed: {exc!r}"
        ) from exc


def assert_round_trip(
    *, original: bytes, compressed: bytes, algorithm: Algorithm,
) -> None:
    """Verify ``decompress(compressed) == original``."""
    if not isinstance(original, (bytes, bytearray)):
        raise CompressionStreamsError("original must be bytes")
    recovered = decompress(compressed, algorithm)
    if recovered != bytes(original):
        raise CompressionStreamsError(
            f"round-trip mismatch: original {len(original)}B vs "
            f"recovered {len(recovered)}B"
        )


def compression_ratio(original_size: int, compressed_size: int) -> float:
    if original_size <= 0:
        raise CompressionStreamsError("original_size must be positive")
    return compressed_size / original_size


def assert_ratio_under(
    *, original_size: int, compressed_size: int, max_ratio: float,
) -> None:
    """Compressed must be at most ``max_ratio`` × original (e.g. 0.5)."""
    if max_ratio <= 0 or max_ratio > 1:
        raise CompressionStreamsError("max_ratio must be in (0, 1]")
    ratio = compression_ratio(original_size, compressed_size)
    if ratio > max_ratio:
        raise CompressionStreamsError(
            f"compression ratio {ratio:.2f} exceeds {max_ratio:.2f} "
            f"(compressed {compressed_size}B vs original {original_size}B)"
        )
