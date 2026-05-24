"""Unit tests for je_web_runner.utils.openapi_to_e2e."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.openapi_to_e2e.generator import (
    OpenAPIGeneratorError,
    generate_tests_from_file,
    generate_tests_from_spec,
    load_spec,
    synthesize_example,
    write_tests_to_dir,
)


_PET_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Pet Store", "version": "1.0"},
    "servers": [{"url": "https://api.pets.example/v1"}],
    "components": {
        "securitySchemes": {
            "bearer": {"type": "http", "scheme": "bearer"},
        },
        "schemas": {
            "Pet": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "id": {"type": "integer", "example": 7},
                    "name": {"type": "string", "example": "Rex"},
                    "tags": {"type": "array",
                              "items": {"type": "string", "example": "good"}},
                },
            },
        },
    },
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "responses": {"200": {"description": "ok"}},
            },
            "post": {
                "operationId": "createPet",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/Pet"},
                    }},
                },
                "responses": {"201": {"description": "created"}},
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "parameters": [
                    {"name": "petId", "in": "path",
                     "required": True, "schema": {"type": "integer", "example": 1}},
                ],
                "responses": {"200": {"description": "ok"}},
            },
            "delete": {
                "operationId": "deletePet",
                "parameters": [
                    {"name": "petId", "in": "path",
                     "required": True, "schema": {"type": "integer"}},
                ],
                "responses": {"204": {"description": "gone"}},
            },
        },
    },
}


class TestSynthesizeExample(unittest.TestCase):

    def test_explicit_example(self):
        result = synthesize_example({}, {"type": "string", "example": "Rex"})
        self.assertEqual(result, "Rex")

    def test_default_fallback(self):
        result = synthesize_example({}, {"type": "integer", "default": 42})
        self.assertEqual(result, 42)

    def test_type_only(self):
        self.assertEqual(synthesize_example({}, {"type": "string"}), "sample")
        self.assertEqual(synthesize_example({}, {"type": "integer"}), 1)

    def test_object_with_required(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "example": "Rex"},
                "age": {"type": "integer", "example": 3},
            },
        }
        result = synthesize_example({}, schema)
        self.assertEqual(result, {"name": "Rex"})

    def test_array(self):
        result = synthesize_example({}, {
            "type": "array",
            "items": {"type": "string", "example": "x"},
        })
        self.assertEqual(result, ["x"])

    def test_enum(self):
        self.assertEqual(synthesize_example({}, {"enum": ["a", "b"]}), "a")

    def test_ref_resolution(self):
        spec = {
            "components": {"schemas": {"X": {"type": "string", "example": "ref"}}},
        }
        result = synthesize_example(spec, {"$ref": "#/components/schemas/X"})
        self.assertEqual(result, "ref")


class TestLoadSpec(unittest.TestCase):

    def test_loads_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "spec.json"
            path.write_text(json.dumps(_PET_SPEC), encoding="utf-8")
            spec = load_spec(path)
            self.assertEqual(spec["info"]["title"], "Pet Store")

    def test_missing_file_raises(self):
        with self.assertRaises(OpenAPIGeneratorError):
            load_spec("/no/such.json")

    def test_invalid_json_yaml_attempt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "spec.json"
            path.write_text("{not json", encoding="utf-8")
            # without pyyaml installed this raises; with pyyaml it may parse
            # as a scalar but our top-level check kicks in.
            try:
                import yaml  # noqa: F401
            except ImportError:
                with self.assertRaises(OpenAPIGeneratorError):
                    load_spec(path)


class TestGenerate(unittest.TestCase):

    def test_happy_path_generated_for_each_method(self):
        result = generate_tests_from_spec(_PET_SPEC, include_negative=False)
        names = {t.name for t in result.tests}
        self.assertIn("listPets__happy", names)
        self.assertIn("createPet__happy", names)
        self.assertIn("getPet__happy", names)
        self.assertIn("deletePet__happy", names)
        self.assertEqual(len(result.tests), 4)

    def test_negative_tests_added(self):
        result = generate_tests_from_spec(_PET_SPEC, include_negative=True)
        names = {t.name for t in result.tests}
        # POST should get a missing-body variant
        self.assertIn("createPet__missing_body", names)
        # GET /pets/{petId} should get a bad path-param variant
        self.assertIn("getPet__bad_path_param", names)

    def test_url_includes_base(self):
        result = generate_tests_from_spec(_PET_SPEC)
        get_pet = next(t for t in result.tests if t.name == "getPet__happy")
        url = get_pet.actions[0][1]["url"]
        self.assertTrue(url.startswith("https://api.pets.example/v1/pets/"))
        self.assertIn("1", url.rsplit("/", 1)[-1])

    def test_auth_header_injected(self):
        result = generate_tests_from_spec(_PET_SPEC)
        first = result.tests[0]
        headers = first.actions[0][1].get("headers") or {}
        self.assertEqual(headers.get("Authorization"), "Bearer ${API_TOKEN}")

    def test_path_prefix_filter(self):
        result = generate_tests_from_spec(
            _PET_SPEC, path_prefix_filter="/pets/{", include_negative=False,
        )
        names = {t.name for t in result.tests}
        self.assertNotIn("listPets__happy", names)
        self.assertIn("getPet__happy", names)

    def test_method_filter(self):
        result = generate_tests_from_spec(
            _PET_SPEC, method_filter={"get"}, include_negative=False,
        )
        for t in result.tests:
            self.assertEqual(t.method, "GET")

    def test_assert_status_action_present(self):
        result = generate_tests_from_spec(_PET_SPEC, include_negative=False)
        for t in result.tests:
            last = t.actions[-1]
            self.assertEqual(last[0], "WR_http_assert_status")

    def test_request_body_synthesised(self):
        result = generate_tests_from_spec(_PET_SPEC)
        create = next(t for t in result.tests if t.name == "createPet__happy")
        body = create.actions[0][1].get("json_body")
        self.assertEqual(body, {"name": "Rex"})

    def test_swagger2_style(self):
        spec = {
            "swagger": "2.0",
            "info": {"title": "Old"},
            "host": "api.old.example",
            "basePath": "/v2",
            "schemes": ["https"],
            "paths": {
                "/items": {
                    "get": {"operationId": "listItems",
                            "responses": {"200": {"description": "ok"}}},
                },
            },
        }
        result = generate_tests_from_spec(spec)
        self.assertEqual(result.base_url, "https://api.old.example/v2")
        self.assertEqual(len(result.tests), 1)

    def test_invalid_spec_raises(self):
        with self.assertRaises(OpenAPIGeneratorError):
            generate_tests_from_spec({})  # no paths
        with self.assertRaises(OpenAPIGeneratorError):
            generate_tests_from_spec("not a dict")  # type: ignore[arg-type]

    def test_unsupported_method_skipped(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "x"},
            "servers": [{"url": "https://x"}],
            "paths": {"/x": {"trace": {"responses": {"200": {"description": "x"}}}}},
        }
        result = generate_tests_from_spec(spec)
        self.assertEqual(len(result.tests), 0)


class TestFromFileAndWrite(unittest.TestCase):

    def test_round_trip_to_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_path = Path(tmpdir) / "spec.json"
            spec_path.write_text(json.dumps(_PET_SPEC), encoding="utf-8")
            result = generate_tests_from_file(spec_path, include_negative=False)
            out_dir = Path(tmpdir) / "out"
            written = write_tests_to_dir(result, out_dir)
            self.assertEqual(len(written), 4)
            for path in written:
                self.assertTrue(path.exists())
                payload = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(payload, list)


if __name__ == "__main__":
    unittest.main()
