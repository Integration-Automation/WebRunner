"""
Supplementary download_verify tests for branches the main file skips:
wait_for_download non-file/non-match skips, JSON/Excel/PDF error paths,
the nested schema validator branches and the remaining assert_download
sub-checks. No optional libs (pypdf/openpyxl) are required.
"""
import hashlib
import json

import pytest

from je_web_runner.utils.download_verify.verifier import (
    DownloadAssertion,
    DownloadVerifyError,
    assert_download,
    assert_json_matches_schema,
    extract_pdf_text,
    read_excel_rows,
    read_json_file,
    wait_for_download,
)


def test_wait_skips_subdir_and_nonmatch(tmp_path):
    (tmp_path / "sub").mkdir()                       # non-file entry
    (tmp_path / "note.txt").write_bytes(b"x")        # does not match .pdf
    clock = {"t": 0.0}
    with pytest.raises(DownloadVerifyError):
        wait_for_download(
            str(tmp_path), pattern=r"\.pdf$",
            timeout=1.0, poll_interval=0.5, stable_for=0.1,
            sleep_fn=lambda s: clock.__setitem__("t", clock["t"] + s),
            time_fn=lambda: clock["t"],
        )


def test_read_json_missing_raises(tmp_path):
    with pytest.raises(DownloadVerifyError):
        read_json_file(tmp_path / "nope.json")


def test_read_json_invalid_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid", encoding="utf-8")
    with pytest.raises(DownloadVerifyError):
        read_json_file(bad)


def test_pdf_missing_file_raises(tmp_path):
    with pytest.raises(DownloadVerifyError):
        extract_pdf_text(tmp_path / "nope.pdf")


def test_excel_missing_file_raises(tmp_path):
    with pytest.raises(DownloadVerifyError):
        read_excel_rows(tmp_path / "nope.xlsx")


def test_excel_without_openpyxl_raises(tmp_path):
    try:
        import openpyxl  # noqa: F401
        pytest.skip("openpyxl is installed; cannot test the missing-lib path")
    except ImportError:
        path = tmp_path / "x.xlsx"
        path.write_bytes(b"PK\x03\x04not-a-real-xlsx")
        with pytest.raises(DownloadVerifyError):
            read_excel_rows(path)


def test_schema_nested_expects_object(tmp_path):
    path = tmp_path / "j.json"
    path.write_text(json.dumps({"address": "not-an-object"}), encoding="utf-8")
    with pytest.raises(DownloadVerifyError):
        assert_json_matches_schema(path, {"address": {"city": "str"}})


def test_schema_unsupported_node(tmp_path):
    path = tmp_path / "j.json"
    path.write_text(json.dumps({"x": 1}), encoding="utf-8")
    with pytest.raises(DownloadVerifyError):
        assert_json_matches_schema(path, {"x": ["unexpected-list-node"]})


def test_assert_download_sha256(tmp_path):
    path = tmp_path / "x.bin"
    path.write_bytes(b"hello")
    digest = hashlib.sha256(b"hello").hexdigest()
    assert_download(path, DownloadAssertion(sha256=digest))
    with pytest.raises(DownloadVerifyError):
        assert_download(path, DownloadAssertion(sha256="0" * 64))


def test_assert_download_json_schema(tmp_path):
    path = tmp_path / "d.json"
    path.write_text(json.dumps({"k": "v"}), encoding="utf-8")
    assert_download(path, DownloadAssertion(json_schema={"k": "str"}))


def test_assert_download_pdf_without_lib(tmp_path):
    try:
        import pypdf  # noqa: F401
        pytest.skip("pypdf is installed; cannot test the missing-lib path")
    except ImportError:
        path = tmp_path / "x.pdf"
        path.write_bytes(b"%PDF-fake")
        with pytest.raises(DownloadVerifyError):
            assert_download(path, DownloadAssertion(pdf_contains="anything"))
