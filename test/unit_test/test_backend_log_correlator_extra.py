"""
Supplementary backend_log_correlator tests for the Loki/Elasticsearch
adapters and the file-fetcher edge branches the main test file omits.
The HTTP adapters are driven with a monkeypatched ``requests`` so no
network is touched; the payload parsers are exercised directly.
"""
import pytest
import requests

from je_web_runner.utils.backend_log_correlator.correlator import (
    BackendLogCorrelatorError,
    _parse_elasticsearch_payload,
    _parse_loki_payload,
    attach_to_failure_bundle,
    fetch_elasticsearch,
    fetch_file_log,
    fetch_loki,
)

_TRACE = "0af7651916cd43dd8448eb211c80319c"


# ---------- Loki payload parser -----------------------------------------

def test_parse_loki_payload_valid():
    payload = {"data": {"result": [
        {"stream": {"level": "error", "service": "api", "span_id": "s1", "env": "prod"},
         "values": [["1700000000", "boom"], ["1700000001", "again"]]},
    ]}}
    logs = _parse_loki_payload(payload)
    assert len(logs) == 2
    assert logs[0].level == "error"
    assert logs[0].service == "api"
    assert logs[0].extra == {"env": "prod"}


def test_parse_loki_payload_non_dict_returns_empty():
    assert _parse_loki_payload("nope") == []


def test_parse_loki_payload_skips_malformed_entries():
    payload = {"data": {"result": [
        {"stream": {}, "values": [["only-one-element"], "not-a-list"]},
    ]}}
    assert _parse_loki_payload(payload) == []


# ---------- Elasticsearch payload parser --------------------------------

def test_parse_es_payload_valid():
    payload = {"hits": {"hits": [
        {"_source": {"message": "m", "level": "WARN", "trace_id": _TRACE}},
        {"_source": "not-a-dict"},
        "not-a-dict-hit",
    ]}}
    logs = _parse_elasticsearch_payload(payload)
    assert len(logs) == 1
    assert logs[0].message == "m"


def test_parse_es_payload_non_dict_returns_empty():
    assert _parse_elasticsearch_payload([]) == []


# ---------- file fetcher edge cases -------------------------------------

def test_file_log_skips_empty_and_invalid_json(tmp_path):
    path = tmp_path / "a.log"
    path.write_text(
        "\n"                                       # empty line -> skipped
        "{bad json but starts with brace\n"        # invalid JSON -> parsed as None
        f'{{"trace_id": "{_TRACE}", "msg": "ok"}}\n',
        encoding="utf-8",
    )
    logs = fetch_file_log(path)(_TRACE)
    assert len(logs) == 1
    assert logs[0].message == "ok"


# ---------- attach: path exists but is a file ---------------------------

def test_attach_path_not_a_directory(tmp_path):
    file_path = tmp_path / "afile"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(BackendLogCorrelatorError):
        attach_to_failure_bundle(file_path, [])


# ---------- HTTP adapters with a faked requests -------------------------

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_loki_success(monkeypatch):
    payload = {"data": {"result": [
        {"stream": {"level": "info"}, "values": [["1", "hello"]]}]}}
    monkeypatch.setattr(requests, "get", lambda *a, **k: _FakeResponse(payload))
    logs = fetch_loki("http://loki:3100")(_TRACE)
    assert len(logs) == 1
    assert logs[0].message == "hello"


def test_fetch_loki_request_error(monkeypatch):
    def boom(*_a, **_k):
        raise requests.RequestException("loki down")

    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(BackendLogCorrelatorError):
        fetch_loki("http://loki:3100")(_TRACE)


def test_fetch_elasticsearch_success(monkeypatch):
    payload = {"hits": {"hits": [{"_source": {"message": "es-line"}}]}}
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResponse(payload))
    logs = fetch_elasticsearch("http://es:9200", "logs-*")(_TRACE)
    assert len(logs) == 1
    assert logs[0].message == "es-line"


def test_fetch_elasticsearch_request_error(monkeypatch):
    def boom(*_a, **_k):
        raise requests.RequestException("es down")

    monkeypatch.setattr(requests, "post", boom)
    with pytest.raises(BackendLogCorrelatorError):
        fetch_elasticsearch("http://es:9200", "logs-*")(_TRACE)
