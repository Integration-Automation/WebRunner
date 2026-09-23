"""Encoding policy of ``WebRunnerLoggingHandler`` (``WEBRunner.log``).

Without an explicit ``encoding`` the handler opens its file with the platform's
locale codec -- cp950 on a Traditional-Chinese Windows box -- so a non-ASCII
record either lands as mojibake or, when a character is outside the code page,
is dropped: ``logging`` swallows the ``UnicodeEncodeError`` into a
"--- Logging error ---" notice on stderr. Jeffrey_RPA tees UTF-8 lines into the
same file, so both writers have to agree on UTF-8 (WebRunner ``progress.md`` #1,
workspace item X-2).
"""
import inspect
import io
import logging
from contextlib import redirect_stderr

import pytest

from je_web_runner.utils.logging.loggin_instance import WebRunnerLoggingHandler

# CJK, a character outside cp950 (U+2810 braille) and an emoji outside the BMP.
_NON_ASCII = "中文 日本語 braille ⠐ emoji \U0001F600"


def _normalised(encoding: str) -> str:
    return encoding.lower().replace("-", "").replace("_", "")


@pytest.fixture
def handler(tmp_path):
    made = WebRunnerLoggingHandler(filename=str(tmp_path / "web_runner.log"))
    yield made
    made.close()


def test_default_encoding_is_utf8():
    default = inspect.signature(WebRunnerLoggingHandler).parameters["encoding"].default
    assert _normalised(default) == "utf8"  # nosec B101


def test_stream_is_utf8_not_the_platform_default(handler):
    assert _normalised(handler.stream.encoding) == "utf8"  # nosec B101


def test_non_ascii_record_is_written_as_utf8(handler, tmp_path):
    log = logging.getLogger("test_web_runner_logging_encoding")
    log.setLevel(logging.DEBUG)
    log.propagate = False
    log.addHandler(handler)
    try:
        captured = io.StringIO()
        with redirect_stderr(captured):
            log.warning(_NON_ASCII)
            handler.flush()
    finally:
        log.removeHandler(handler)

    assert "--- Logging error ---" not in captured.getvalue()  # nosec B101
    written = (tmp_path / "web_runner.log").read_bytes().decode("utf-8")
    assert _NON_ASCII in written  # nosec B101


def test_encoding_is_still_overridable(tmp_path):
    made = WebRunnerLoggingHandler(filename=str(tmp_path / "utf16.log"), encoding="utf-16")
    try:
        assert _normalised(made.stream.encoding) == "utf16"  # nosec B101
    finally:
        made.close()
