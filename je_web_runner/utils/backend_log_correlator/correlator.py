"""
用 ``otel_bridge`` 注入的 traceparent,把後端 log 拉進 failure bundle。
Given a W3C trace id (the 32-hex middle of a ``traceparent`` header)
captured during a UI run, ask a log backend for matching lines and merge
them into the failure artifact.

Adapters provided out of the box:

* :func:`fetch_loki` — Grafana Loki ``/loki/api/v1/query_range``
* :func:`fetch_elasticsearch` — Elasticsearch ``_search`` with ``trace_id``
* :func:`fetch_file_log` — plain text / JSON-lines log file (works offline)

All adapters return the same :class:`CorrelatedLog` list, which
:func:`attach_to_failure_bundle` then writes alongside the bundle's
existing artifacts.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class BackendLogCorrelatorError(WebRunnerException):
    """Raised on backend errors, malformed responses, or bad input."""


_TRACEPARENT_RE = re.compile(
    r"^(?P<ver>[0-9a-f]{2})-(?P<trace>[0-9a-f]{32})-(?P<span>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$",
    re.IGNORECASE,
)
_TRACE_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


# ---------- data ---------------------------------------------------------

@dataclass
class CorrelatedLog:
    """One log line correlated to a trace."""

    timestamp: str
    level: str
    message: str
    service: str | None = None
    span_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


LogFetcher = Callable[[str], list[CorrelatedLog]]
"""Signature: ``fetcher(trace_id) -> [CorrelatedLog, ...]``."""


# ---------- traceparent helpers -----------------------------------------

def parse_traceparent(header_value: str) -> str:
    """Extract the 32-hex trace id from a W3C ``traceparent`` header."""
    if not isinstance(header_value, str) or not header_value:
        raise BackendLogCorrelatorError("traceparent must be a non-empty string")
    match = _TRACEPARENT_RE.match(header_value.strip())
    if not match:
        raise BackendLogCorrelatorError(f"malformed traceparent: {header_value!r}")
    return match.group("trace").lower()


def validate_trace_id(trace_id: str) -> str:
    """Return the trace id normalised to lowercase hex; raise if malformed."""
    if not isinstance(trace_id, str) or not _TRACE_ID_RE.match(trace_id):
        raise BackendLogCorrelatorError(
            f"trace_id must be 32 hex chars, got {trace_id!r}"
        )
    return trace_id.lower()


# ---------- file adapter (offline / tests) -------------------------------

def fetch_file_log(
    log_path: str | Path,
    *,
    trace_field: str = "trace_id",
    fallback_to_substring: bool = True,
) -> LogFetcher:
    """
    Build a fetcher that reads ``log_path`` as JSON-lines (preferred) or
    plain text. Lines whose JSON ``trace_field`` equals the requested
    trace id are returned. For plain text, substring match is used when
    ``fallback_to_substring`` is true.
    """
    path = Path(log_path)
    if not path.exists():
        raise BackendLogCorrelatorError(f"log file not found: {path}")

    def _fetch(trace_id: str) -> list[CorrelatedLog]:
        wanted = validate_trace_id(trace_id)
        out: list[CorrelatedLog] = []
        with open(path, encoding="utf-8") as fp:
            for line in fp:
                stripped = line.rstrip("\r\n")
                if not stripped:
                    continue
                record = _try_parse_json_line(stripped)
                if record is not None:
                    if str(record.get(trace_field, "")).lower() == wanted:
                        out.append(_log_from_dict(record))
                elif fallback_to_substring and wanted in stripped.lower():
                    out.append(CorrelatedLog(
                        timestamp="", level="info", message=stripped,
                    ))
        return out

    return _fetch


def _try_parse_json_line(line: str) -> dict[str, Any] | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        loaded = json.loads(line)
    except ValueError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _log_from_dict(record: dict[str, Any]) -> CorrelatedLog:
    return CorrelatedLog(
        timestamp=str(record.get("timestamp") or record.get("ts") or ""),
        level=str(record.get("level") or record.get("severity") or "info"),
        message=str(record.get("message") or record.get("msg") or ""),
        service=record.get("service") or record.get("app"),
        span_id=record.get("span_id"),
        extra={
            k: v for k, v in record.items()
            if k not in {
                "timestamp", "ts", "level", "severity", "message", "msg",
                "service", "app", "span_id", "trace_id",
            }
        },
    )


# ---------- Loki adapter -------------------------------------------------

def _require_requests() -> Any:
    try:
        import requests  # type: ignore[import-not-found]
        return requests
    except ImportError as error:
        raise BackendLogCorrelatorError(
            "requests is required for Loki/Elasticsearch fetchers. "
            "Install: pip install requests"
        ) from error


def fetch_loki(
    base_url: str,
    *,
    label: str = "trace_id",
    timeout: float = 15.0,
    limit: int = 1000,
) -> LogFetcher:
    """Build a fetcher that queries Grafana Loki by label-equals match."""
    requests = _require_requests()
    url = base_url.rstrip("/") + "/loki/api/v1/query_range"

    def _fetch(trace_id: str) -> list[CorrelatedLog]:
        wanted = validate_trace_id(trace_id)
        params = {"query": f'{{{label}="{wanted}"}}', "limit": int(limit)}
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise BackendLogCorrelatorError(f"loki fetch failed: {error!r}") from error
        return _parse_loki_payload(payload)

    return _fetch


def _parse_loki_payload(payload: Any) -> list[CorrelatedLog]:
    out: list[CorrelatedLog] = []
    if not isinstance(payload, dict):
        return out
    streams = ((payload.get("data") or {}).get("result")) or []
    for stream in streams:
        labels = stream.get("stream") or {}
        for entry in stream.get("values") or []:
            if not isinstance(entry, list) or len(entry) != 2:
                continue
            ts_ns, line = entry
            out.append(CorrelatedLog(
                timestamp=str(ts_ns),
                level=str(labels.get("level") or "info"),
                message=str(line),
                service=labels.get("service") or labels.get("app"),
                span_id=labels.get("span_id"),
                extra={k: v for k, v in labels.items()
                       if k not in {"level", "service", "app", "span_id"}},
            ))
    return out


# ---------- Elasticsearch adapter ---------------------------------------

def fetch_elasticsearch(
    base_url: str,
    index: str,
    *,
    trace_field: str = "trace_id",
    timeout: float = 15.0,
    size: int = 500,
) -> LogFetcher:
    """Build a fetcher that does ``GET {index}/_search`` with a term query."""
    requests = _require_requests()
    url = f"{base_url.rstrip('/')}/{index}/_search"

    def _fetch(trace_id: str) -> list[CorrelatedLog]:
        wanted = validate_trace_id(trace_id)
        body = {"size": int(size), "query": {"term": {trace_field: wanted}}}
        try:
            response = requests.post(url, json=body, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise BackendLogCorrelatorError(f"elastic fetch failed: {error!r}") from error
        return _parse_elasticsearch_payload(payload)

    return _fetch


def _parse_elasticsearch_payload(payload: Any) -> list[CorrelatedLog]:
    if not isinstance(payload, dict):
        return []
    hits = ((payload.get("hits") or {}).get("hits")) or []
    out: list[CorrelatedLog] = []
    for hit in hits:
        source = hit.get("_source") if isinstance(hit, dict) else None
        if isinstance(source, dict):
            out.append(_log_from_dict(source))
    return out


# ---------- bundle integration ------------------------------------------

def correlate(
    trace_id_or_header: str,
    fetchers: Sequence[LogFetcher],
) -> list[CorrelatedLog]:
    """
    Resolve ``trace_id_or_header`` (raw id or full traceparent) and call
    every fetcher in turn, concatenating their results.
    """
    if not fetchers:
        raise BackendLogCorrelatorError("at least one fetcher is required")
    raw = trace_id_or_header.strip() if isinstance(trace_id_or_header, str) else ""
    trace_id = parse_traceparent(raw) if "-" in raw else validate_trace_id(raw)
    merged: list[CorrelatedLog] = []
    for fetcher in fetchers:
        try:
            merged.extend(fetcher(trace_id))
        except BackendLogCorrelatorError:
            raise
        except Exception as error:
            web_runner_logger.warning(f"correlator fetcher failed: {error!r}")
    return merged


def attach_to_failure_bundle(
    bundle_dir: str | Path,
    logs: Iterable[CorrelatedLog],
    *,
    filename: str = "backend_logs.json",
) -> Path:
    """Write ``logs`` as JSON into an existing failure-bundle directory."""
    bundle = Path(bundle_dir)
    if not bundle.exists():
        raise BackendLogCorrelatorError(f"failure bundle dir not found: {bundle}")
    if not bundle.is_dir():
        raise BackendLogCorrelatorError(f"failure bundle path is not a directory: {bundle}")
    payload = [log.to_dict() for log in logs]
    target = bundle / filename
    with open(target, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    return target
