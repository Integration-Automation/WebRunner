import tempfile
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

from je_web_runner.utils.visual_review import (
    VisualReviewError,
    VisualReviewServer,
    accept_baseline,
    list_diffs,
)
from je_web_runner.utils.visual_review.review_server import render_index


class TestListDiffs(unittest.TestCase):

    def test_status_for_match_diff_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base"
            curr = Path(tmpdir) / "curr"
            base.mkdir(); curr.mkdir()
            (base / "same.png").write_bytes(b"same")
            (curr / "same.png").write_bytes(b"same")
            (base / "drift.png").write_bytes(b"a")
            (curr / "drift.png").write_bytes(b"b")
            (base / "only-baseline.png").write_bytes(b"x")
            (curr / "only-current.png").write_bytes(b"y")
            statuses = {d["name"]: d["status"] for d in list_diffs(str(base), str(curr))}
            self.assertEqual(statuses["same.png"], "match")
            self.assertEqual(statuses["drift.png"], "diff")
            self.assertEqual(statuses["only-baseline.png"], "missing-current")
            self.assertEqual(statuses["only-current.png"], "missing-baseline")


class TestAcceptBaseline(unittest.TestCase):

    def test_copies_current_to_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base"
            curr = Path(tmpdir) / "curr"
            base.mkdir(); curr.mkdir()
            (curr / "x.png").write_bytes(b"new")
            target = accept_baseline(str(base), str(curr), "x.png")
            self.assertTrue(target.is_file())
            self.assertEqual((base / "x.png").read_bytes(), b"new")

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base"
            curr = Path(tmpdir) / "curr"
            base.mkdir(); curr.mkdir()
            with self.assertRaises(VisualReviewError):
                accept_baseline(str(base), str(curr), "../escape.png")

    def test_missing_current_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base"; base.mkdir()
            curr = Path(tmpdir) / "curr"; curr.mkdir()
            with self.assertRaises(VisualReviewError):
                accept_baseline(str(base), str(curr), "missing.png")


class TestRenderIndex(unittest.TestCase):

    def test_includes_status_classes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base"; base.mkdir()
            curr = Path(tmpdir) / "curr"; curr.mkdir()
            (base / "drift.png").write_bytes(b"a")
            (curr / "drift.png").write_bytes(b"b")
            html = render_index(str(base), str(curr))
            self.assertIn("Visual review", html)
            self.assertIn("drift.png", html)
            self.assertIn("class='diff'", html)


class TestVisualReviewServer(unittest.TestCase):

    def test_index_then_accept(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base"; base.mkdir()
            curr = Path(tmpdir) / "curr"; curr.mkdir()
            (base / "drift.png").write_bytes(b"a")
            (curr / "drift.png").write_bytes(b"b")
            server = VisualReviewServer(str(base), str(curr))
            url = server.start()
            try:
                with urllib.request.urlopen(url + "/", timeout=2) as response:  # nosec B310
                    body = response.read().decode("utf-8")
                self.assertIn("drift.png", body)
                # Accept
                payload = urllib.parse.urlencode({"name": "drift.png"}).encode("utf-8")
                request = urllib.request.Request(url + "/accept", data=payload, method="POST")
                request.add_header("Content-Type", "application/x-www-form-urlencoded")
                opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
                with opener.open(request, timeout=2):  # nosec B310
                    pass
                self.assertEqual((base / "drift.png").read_bytes(), b"b")
                self.assertEqual(server.accepted, ["drift.png"])
            finally:
                server.stop()

    def test_unknown_path_404(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base"; base.mkdir()
            curr = Path(tmpdir) / "curr"; curr.mkdir()
            server = VisualReviewServer(str(base), str(curr))
            url = server.start()
            try:
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(url + "/nope", timeout=2)  # nosec B310
                self.assertEqual(ctx.exception.code, 404)
            finally:
                server.stop()


if __name__ == "__main__":
    unittest.main()
