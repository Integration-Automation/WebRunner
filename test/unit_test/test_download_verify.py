"""Unit tests for je_web_runner.utils.download_verify."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from je_web_runner.utils.download_verify.verifier import (
    DownloadAssertion,
    DownloadVerifyError,
    assert_csv_columns,
    assert_csv_row_count,
    assert_download,
    assert_file_sha256,
    assert_json_matches_schema,
    read_csv_rows,
    read_json_file,
    sha256_of_file,
    wait_for_download,
)


class TestSha256(unittest.TestCase):

    def test_hash_matches_hashlib(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "x.bin"
            path.write_bytes(b"hello world")
            expected = hashlib.sha256(b"hello world").hexdigest()
            self.assertEqual(sha256_of_file(path), expected)

    def test_missing_file_raises(self):
        with self.assertRaises(DownloadVerifyError):
            sha256_of_file("/no/such")

    def test_assert_passes_and_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "x.bin"
            path.write_bytes(b"hi")
            digest = hashlib.sha256(b"hi").hexdigest()
            assert_file_sha256(path, digest)
            with self.assertRaises(DownloadVerifyError):
                assert_file_sha256(path, "0" * 64)


class TestWaitForDownload(unittest.TestCase):

    def test_returns_when_stable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "out.pdf"
            target.write_bytes(b"%PDF-fake-content")
            path = wait_for_download(
                tmpdir, pattern=r"\.pdf$",
                timeout=2, poll_interval=0.05, stable_for=0.01,
                sleep_fn=lambda _s: None,
            )
            self.assertEqual(path.name, "out.pdf")

    def test_excludes_partial_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            partial = Path(tmpdir) / "out.pdf.crdownload"
            partial.write_bytes(b"partial")
            clock = {"now": 0.0}

            def fake_time():
                return clock["now"]

            def fake_sleep(s):
                clock["now"] += s

            with self.assertRaises(DownloadVerifyError):
                wait_for_download(
                    tmpdir, pattern=r"\.pdf$",
                    timeout=1, poll_interval=0.5, stable_for=0.1,
                    sleep_fn=fake_sleep, time_fn=fake_time,
                )

    def test_missing_dir_raises(self):
        with self.assertRaises(DownloadVerifyError):
            wait_for_download("/no/dir")


class TestReadCsv(unittest.TestCase):

    def test_reads_rows_with_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a.csv"
            path.write_text("name,age\nAlice,30\nBob,25\n", encoding="utf-8")
            rows = read_csv_rows(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["name"], "Alice")

    def test_missing_file_raises(self):
        with self.assertRaises(DownloadVerifyError):
            read_csv_rows("/no/such.csv")


class TestCsvAssertions(unittest.TestCase):

    def test_columns_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a.csv"
            path.write_text("name,age\nA,1\n", encoding="utf-8")
            assert_csv_columns(path, ["name", "age"])

    def test_missing_column_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a.csv"
            path.write_text("name\nA\n", encoding="utf-8")
            with self.assertRaises(DownloadVerifyError):
                assert_csv_columns(path, ["name", "age"])

    def test_empty_csv_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a.csv"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(DownloadVerifyError):
                assert_csv_columns(path, ["a"])

    def test_row_count_bounds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a.csv"
            path.write_text("a\n1\n2\n3\n", encoding="utf-8")
            self.assertEqual(assert_csv_row_count(path, minimum=2, maximum=5), 3)
            with self.assertRaises(DownloadVerifyError):
                assert_csv_row_count(path, minimum=10)
            with self.assertRaises(DownloadVerifyError):
                assert_csv_row_count(path, maximum=1)


class TestJsonSchema(unittest.TestCase):

    def test_passing_schema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "j.json"
            path.write_text(json.dumps({
                "name": "Alice", "age": 30,
                "address": {"city": "Seoul"},
            }), encoding="utf-8")
            assert_json_matches_schema(path, {
                "name": "str", "age": "int",
                "address": {"city": "str"},
            })

    def test_type_mismatch_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "j.json"
            path.write_text(json.dumps({"name": 1}), encoding="utf-8")
            with self.assertRaises(DownloadVerifyError):
                assert_json_matches_schema(path, {"name": "str"})

    def test_missing_key_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "j.json"
            path.write_text(json.dumps({}), encoding="utf-8")
            with self.assertRaises(DownloadVerifyError):
                assert_json_matches_schema(path, {"name": "str"})

    def test_any_type_accepts_anything(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "j.json"
            path.write_text(json.dumps({"x": [1, 2, 3]}), encoding="utf-8")
            assert_json_matches_schema(path, {"x": "any"})

    def test_unknown_type_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "j.json"
            path.write_text(json.dumps({"x": 1}), encoding="utf-8")
            with self.assertRaises(DownloadVerifyError):
                assert_json_matches_schema(path, {"x": "integer"})

    def test_read_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "j.json"
            path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            self.assertEqual(read_json_file(path), [1, 2, 3])


class TestPdf(unittest.TestCase):

    def test_extract_with_no_pdf_libs_raises(self):
        from je_web_runner.utils.download_verify import verifier
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "x.pdf"
            path.write_bytes(b"%PDF-fake")
            import builtins
            original_import = builtins.__import__

            def fake_import(name, *args, **kwargs):
                if name in ("pypdf", "pdfplumber"):
                    raise ImportError("simulated")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=fake_import):
                with self.assertRaises(DownloadVerifyError):
                    verifier.extract_pdf_text(path)

    def test_extract_with_pypdf(self):
        try:
            import pypdf  # noqa: F401
        except ImportError:
            self.skipTest("pypdf not installed")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "x.pdf"
            _write_minimal_pdf(path, "Hello WebRunner")
            from je_web_runner.utils.download_verify.verifier import (
                assert_pdf_contains,
                extract_pdf_text,
            )
            text = extract_pdf_text(path)
            self.assertIn("Hello WebRunner", text)
            assert_pdf_contains(path, "WebRunner")
            with self.assertRaises(DownloadVerifyError):
                assert_pdf_contains(path, "NotPresent")


class TestAssertDownload(unittest.TestCase):

    def test_filename_pattern_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report-2026.csv"
            path.write_text("a,b\n1,2\n", encoding="utf-8")
            assert_download(path, DownloadAssertion(
                filename_pattern=r"report-\d+\.csv",
                csv_columns=["a", "b"],
                min_size_bytes=1,
            ))

    def test_filename_mismatch_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.csv"
            path.write_text("a\n1\n", encoding="utf-8")
            with self.assertRaises(DownloadVerifyError):
                assert_download(path, DownloadAssertion(
                    filename_pattern=r"^summary-",
                ))

    def test_size_bounds_raise(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "x.bin"
            path.write_bytes(b"x")
            with self.assertRaises(DownloadVerifyError):
                assert_download(path, DownloadAssertion(min_size_bytes=10))
            with self.assertRaises(DownloadVerifyError):
                assert_download(path, DownloadAssertion(max_size_bytes=0))

    def test_missing_file_raises(self):
        with self.assertRaises(DownloadVerifyError):
            assert_download("/no/such", DownloadAssertion())


def _write_minimal_pdf(path: Path, text: str) -> None:
    """Use pypdf to write a single-page PDF containing ``text``."""
    try:
        from pypdf import PdfWriter
    except ImportError:
        path.write_bytes(b"%PDF-")
        return
    try:
        from reportlab.pdfgen import canvas  # type: ignore[import-not-found]
        from io import BytesIO
        buf = BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(50, 800, text)
        c.showPage()
        c.save()
        path.write_bytes(buf.getvalue())
    except ImportError:
        # Fallback: stitch together a near-minimal text page via pypdf
        # (PdfWriter already imported above).
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        with open(path, "wb") as fp:
            writer.write(fp)


if __name__ == "__main__":
    unittest.main()
