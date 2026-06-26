"""Unit tests for the JSON reformat helper (json_format.json_process)."""
import json

import pytest

from je_web_runner.utils.exception.exceptions import WebRunnerJsonException
from je_web_runner.utils.json.json_format.json_process import reformat_json


def test_reformat_valid_json_string_sorts_and_indents():
    result = reformat_json('{"b": 1, "a": 2}')
    # Round-trips to the same data.
    assert json.loads(result) == {"a": 2, "b": 1}
    # sort_keys=True puts "a" before "b".
    assert result.index('"a"') < result.index('"b"')
    # indent=4 produces a multi-line document.
    assert "\n" in result


def test_reformat_accepts_python_object():
    # Non-string input goes through the TypeError fallback branch.
    result = reformat_json({"x": [1, 2, 3]})
    assert json.loads(result) == {"x": [1, 2, 3]}


def test_reformat_invalid_json_raises_decode_error():
    with pytest.raises(json.JSONDecodeError):
        reformat_json("{not valid json")


def test_reformat_non_serializable_raises_webrunner_json_exception():
    # A set is neither a JSON string nor JSON-serializable, so both the
    # loads() and the dumps() fallback raise TypeError.
    with pytest.raises(WebRunnerJsonException):
        reformat_json({1, 2, 3})
