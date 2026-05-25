"""Unit tests for je_web_runner.utils.har_to_openapi."""
import json
import unittest

from je_web_runner.utils.har_to_openapi.converter import (
    HarToOpenapiError,
    assert_spec_minimum_coverage,
    convert,
)


def _entry(url, method="GET", status=200, body=None):
    return {
        "request": {"url": url, "method": method},
        "response": {
            "status": status,
            "content": {"text": json.dumps(body) if body is not None else ""},
        },
    }


def _har(*entries):
    return {"log": {"entries": list(entries)}}


class TestConvert(unittest.TestCase):

    def test_basic(self):
        spec = convert(_har(_entry("https://api/users/42",
                                    body={"id": 42, "name": "x"})))
        self.assertIn("/users/{id}", spec["paths"])
        op = spec["paths"]["/users/{id}"]["get"]
        schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("name", schema["properties"])

    def test_uuid_collapses(self):
        spec = convert(_har(_entry(
            "https://api/orders/9e107d9d-372b-4f72-9f49-2c7c4be32e2c",
        )))
        self.assertIn("/orders/{uuid}", spec["paths"])

    def test_query_params(self):
        spec = convert(_har(_entry("https://api/search?q=foo&lang=ja")))
        params = spec["paths"]["/search"]["get"]["parameters"]
        names = {p["name"] for p in params}
        self.assertEqual(names, {"q", "lang"})

    def test_multiple_methods(self):
        spec = convert(_har(
            _entry("https://api/x", method="GET"),
            _entry("https://api/x", method="POST"),
        ))
        self.assertEqual(set(spec["paths"]["/x"].keys()), {"get", "post"})

    def test_bad_har(self):
        with self.assertRaises(HarToOpenapiError):
            convert("nope")

    def test_bad_entries(self):
        with self.assertRaises(HarToOpenapiError):
            convert({"log": {"entries": "nope"}})


class TestCoverage(unittest.TestCase):

    def test_pass(self):
        spec = convert(_har(_entry("https://api/x"), _entry("https://api/y")))
        assert_spec_minimum_coverage(spec, min_paths=2)

    def test_fail(self):
        spec = convert(_har(_entry("https://api/x")))
        with self.assertRaises(HarToOpenapiError):
            assert_spec_minimum_coverage(spec, min_paths=2)

    def test_bad_min(self):
        with self.assertRaises(HarToOpenapiError):
            assert_spec_minimum_coverage({}, min_paths=0)


if __name__ == "__main__":
    unittest.main()
