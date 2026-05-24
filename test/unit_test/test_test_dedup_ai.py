"""Unit tests for je_web_runner.utils.test_dedup_ai."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.test_dedup_ai.dedup import (
    ActionFile,
    DuplicateCluster,
    TestDedupError,
    clusters_markdown,
    load_dir,
    semantic_clusters,
    stable_fingerprint,
    structural_clusters,
)


def _login_actions(url="https://x", user="alice"):
    return [
        {"WR_to_url": [url]},
        {"WR_input_to_element": ["id", "username", user]},
        {"WR_input_to_element": ["id", "password", "pw"]},
        {"WR_click_element": ["id", "submit"]},
    ]


def _checkout_actions():
    return [
        {"WR_to_url": ["https://shop/"]},
        {"WR_click_element": ["id", "cart"]},
        {"WR_click_element": ["id", "checkout"]},
    ]


def _file(path, actions):
    f = ActionFile(path=path, actions=actions)
    f.fingerprint = stable_fingerprint(actions)  # use the same internals
    return f


class TestStructural(unittest.TestCase):

    def test_finds_exact_duplicates(self):
        files = [
            ActionFile.load(self._write_file("a.json", _login_actions("https://x", "a"))),
            ActionFile.load(self._write_file("b.json", _login_actions("https://y", "b"))),
            ActionFile.load(self._write_file("c.json", _checkout_actions())),
        ]
        clusters = structural_clusters(files)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].members), 2)

    def _write_file(self, name, actions):
        path = Path(self._tmpdir) / name
        path.write_text(json.dumps(actions), encoding="utf-8")
        return path

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._tmpdir = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def test_singletons_dropped(self):
        files = [
            ActionFile.load(self._write_file("a.json", _login_actions())),
            ActionFile.load(self._write_file("b.json", _checkout_actions())),
        ]
        self.assertEqual(structural_clusters(files), [])

    def test_empty_input_rejected(self):
        with self.assertRaises(TestDedupError):
            structural_clusters([])


class TestLoading(unittest.TestCase):

    def test_load_missing(self):
        with self.assertRaises(TestDedupError):
            ActionFile.load("/no/such/file.json")

    def test_load_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text("not json", encoding="utf-8")
            with self.assertRaises(TestDedupError):
                ActionFile.load(p)

    def test_load_non_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.json"
            p.write_text("{\"x\":1}", encoding="utf-8")
            with self.assertRaises(TestDedupError):
                ActionFile.load(p)

    def test_load_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.json").write_text(json.dumps(_login_actions()), encoding="utf-8")
            (Path(tmp) / "b.json").write_text(json.dumps(_checkout_actions()), encoding="utf-8")
            files = load_dir(tmp)
            self.assertEqual(len(files), 2)

    def test_load_dir_missing(self):
        with self.assertRaises(TestDedupError):
            load_dir("/no/such/dir")


class TestSemantic(unittest.TestCase):

    def test_clusters_by_threshold(self):
        files = [
            _file("a.json", _login_actions()),
            _file("b.json", _login_actions("https://y")),
            _file("c.json", _checkout_actions()),
        ]
        # Stub embedder: identical for login files, different for checkout
        def embed(text):
            return [1.0, 0.0] if "WR_input" in text else [0.0, 1.0]

        clusters = semantic_clusters(files, embed, similarity_threshold=0.95)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0].members), 2)

    def test_no_clusters_when_threshold_too_high(self):
        files = [
            _file("a.json", _login_actions()),
            _file("b.json", _login_actions()),
        ]
        # Slight noise → cosine = 0.99
        vectors = [[1.0, 0.0], [0.99, 0.1414]]
        ptr = {"i": 0}

        def embed(_):
            v = vectors[ptr["i"]]
            ptr["i"] += 1
            return v
        clusters = semantic_clusters(files, embed, similarity_threshold=0.999)
        self.assertEqual(clusters, [])

    def test_bad_threshold(self):
        with self.assertRaises(TestDedupError):
            semantic_clusters([_file("a", _login_actions())], lambda _: [1.0],
                              similarity_threshold=0.0)
        with self.assertRaises(TestDedupError):
            semantic_clusters([_file("a", _login_actions())], lambda _: [1.0],
                              similarity_threshold=1.5)

    def test_bad_vector(self):
        with self.assertRaises(TestDedupError):
            semantic_clusters([_file("a", _login_actions())], lambda _: "not vector")

    def test_embedder_exception(self):
        def bad(_):
            raise RuntimeError("rate limit")
        with self.assertRaises(TestDedupError):
            semantic_clusters([_file("a", _login_actions())], bad)

    def test_empty_rejected(self):
        with self.assertRaises(TestDedupError):
            semantic_clusters([], lambda _: [1.0])


class TestFingerprint(unittest.TestCase):

    def test_stable_across_calls(self):
        a = stable_fingerprint(_login_actions())
        b = stable_fingerprint(_login_actions("https://different", "different"))
        # Same structure, different data → same fingerprint
        self.assertEqual(a, b)

    def test_different_for_different_structure(self):
        self.assertNotEqual(
            stable_fingerprint(_login_actions()),
            stable_fingerprint(_checkout_actions()),
        )

    def test_rejects_bad_input(self):
        with self.assertRaises(TestDedupError):
            stable_fingerprint("not a list")  # type: ignore[arg-type]
        with self.assertRaises(TestDedupError):
            stable_fingerprint([{"a": "b", "extra": 1}])


class TestMarkdown(unittest.TestCase):

    def test_empty(self):
        self.assertIn("No duplicate", clusters_markdown([]))

    def test_with_clusters(self):
        cluster = DuplicateCluster(
            mode="structural", members=["a.json", "b.json"],
            representative="a.json",
        )
        md = clusters_markdown([cluster])
        self.assertIn("a.json", md)
        self.assertIn("structural", md)


if __name__ == "__main__":
    unittest.main()
