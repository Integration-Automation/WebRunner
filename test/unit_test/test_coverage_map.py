import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.coverage_map import (
    CoverageMapError,
    build_coverage_map,
    coverage_for_routes,
    render_markdown,
)
from je_web_runner.utils.coverage_map.coverage import normalise_path


def _write_actions(path, actions):
    Path(path).write_text(json.dumps(actions), encoding="utf-8")


class TestNormalisePath(unittest.TestCase):

    def test_strips_query_and_fragment(self):
        self.assertEqual(normalise_path("/foo?a=1#frag"), "/foo")

    def test_replaces_numeric_segment(self):
        self.assertEqual(normalise_path("/users/42"), "/users/:id")

    def test_replaces_uuid_segment(self):
        self.assertEqual(
            normalise_path("/orders/0a1b2c3d-1111-2222-3333-44556677"),
            "/orders/:id",
        )

    def test_preserves_alpha_segments(self):
        self.assertEqual(normalise_path("/auth/login"), "/auth/login")

    def test_no_normalisation(self):
        self.assertEqual(
            normalise_path("/users/42", normalise_params=False),
            "/users/42",
        )


class TestBuildCoverageMap(unittest.TestCase):

    def test_indexes_navigation_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            login = Path(tmpdir) / "login.json"
            checkout = Path(tmpdir) / "checkout.json"
            _write_actions(login, [
                ["WR_to_url", {"url": "https://example.com/auth/login"}],
            ])
            _write_actions(checkout, [
                ["WR_pw_to_url", {"url": "https://example.com/checkout?step=2"}],
                ["WR_to_url", {"url": "https://example.com/users/42"}],
            ])
            coverage = build_coverage_map(tmpdir)
            self.assertEqual(coverage.files_for("/auth/login"), [str(login)])
            self.assertEqual(coverage.files_for("/checkout"), [str(checkout)])
            self.assertEqual(coverage.files_for("/users/:id"), [str(checkout)])

    def test_invalid_directory(self):
        with self.assertRaises(CoverageMapError):
            build_coverage_map("does/not/exist")

    def test_skips_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "bad.json").write_text("not json", encoding="utf-8")
            ok = Path(tmpdir) / "ok.json"
            _write_actions(ok, [["WR_to_url", {"url": "https://x/y"}]])
            coverage = build_coverage_map(tmpdir)
            self.assertEqual(coverage.files_for("/y"), [str(ok)])

    def test_no_normalisation_keeps_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ok = Path(tmpdir) / "ok.json"
            _write_actions(ok, [["WR_to_url", {"url": "https://x/users/42"}]])
            coverage = build_coverage_map(tmpdir, normalise_params=False)
            self.assertIn("/users/42", coverage.all_routes())


class TestCoverageForRoutes(unittest.TestCase):

    def test_returns_uncovered_route(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            login = Path(tmpdir) / "login.json"
            _write_actions(login, [["WR_to_url", {"url": "https://x/auth/login"}]])
            coverage = build_coverage_map(tmpdir)
            mapping = coverage_for_routes(
                coverage, ["/auth/login", "/checkout"],
            )
            self.assertEqual(mapping["/auth/login"], [str(login)])
            self.assertEqual(mapping["/checkout"], [])

    def test_uncovered_helper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            login = Path(tmpdir) / "login.json"
            _write_actions(login, [["WR_to_url", {"url": "https://x/auth/login"}]])
            coverage = build_coverage_map(tmpdir)
            uncovered = coverage.uncovered(["/auth/login", "/admin", "/cart"])
            self.assertEqual(uncovered, ["/admin", "/cart"])


class TestRenderMarkdown(unittest.TestCase):

    def test_renders_table_with_uncovered(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            login = Path(tmpdir) / "login.json"
            _write_actions(login, [["WR_to_url", {"url": "https://x/auth/login"}]])
            coverage = build_coverage_map(tmpdir)
            text = render_markdown(coverage, declared_routes=["/auth/login", "/admin"])
            self.assertIn("/auth/login", text)
            self.assertIn("_uncovered_", text)


if __name__ == "__main__":
    unittest.main()
