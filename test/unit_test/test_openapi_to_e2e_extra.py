"""
Supplementary openapi_to_e2e tests for the spec-engine edge branches the
main file omits: YAML loading (happy / parse-error / non-mapping), the
``examples`` (plural) synthesis forms, $ref resolution edge cases and the
non-dict / empty-array synthesis paths.
"""
import pytest

from je_web_runner.utils.openapi_to_e2e.generator import (
    OpenAPIGeneratorError,
    _maybe_resolve,
    _resolve_ref,
    load_spec,
    synthesize_example,
)


# ---------- YAML loading -------------------------------------------------

def test_load_yaml_spec(tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "spec.yaml"
    path.write_text(
        "openapi: 3.0.0\ninfo:\n  title: Y\n  version: '1'\npaths: {}\n",
        encoding="utf-8",
    )
    spec = load_spec(path)
    assert spec["info"]["title"] == "Y"


def test_load_yaml_parse_error_raises(tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "spec.yaml"
    path.write_text("a: [1, 2", encoding="utf-8")  # invalid JSON and invalid YAML
    with pytest.raises(OpenAPIGeneratorError):
        load_spec(path)


def test_load_yaml_non_mapping_raises(tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "spec.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")  # top-level list
    with pytest.raises(OpenAPIGeneratorError):
        load_spec(path)


# ---------- examples (plural) synthesis ---------------------------------

def test_synthesize_examples_dict_with_value():
    assert synthesize_example({}, {"examples": {"ex1": {"value": "hello"}}}) == "hello"


def test_synthesize_examples_dict_without_value():
    assert synthesize_example({}, {"examples": {"ex1": "raw"}}) == "raw"


def test_synthesize_examples_list():
    assert synthesize_example({}, {"examples": ["first", "second"]}) == "first"


# ---------- $ref resolution edge cases ----------------------------------

def test_resolve_ref_bad_format_returns_none():
    assert _resolve_ref({}, "not-a-ref") is None


def test_resolve_ref_missing_node_returns_none():
    assert _resolve_ref({"a": {}}, "#/a/b/c") is None


def test_maybe_resolve_unresolvable_ref_returns_empty_dict():
    assert _maybe_resolve({}, {"$ref": "#/does/not/exist"}) == {}


def test_maybe_resolve_non_dict_passthrough():
    assert _maybe_resolve({}, "scalar") == "scalar"


# ---------- synthesis fallbacks -----------------------------------------

def test_synthesize_non_dict_schema_returns_none():
    assert synthesize_example({}, "not-a-schema") is None


def test_synthesize_array_without_items_returns_empty():
    assert synthesize_example({}, {"type": "array"}) == []
