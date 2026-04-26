import unittest

from je_web_runner.utils.contract_testing import (
    ContractError,
    validate_against_openapi,
    validate_response,
)
from je_web_runner.utils.contract_testing.contract import assert_valid


class TestValidateResponse(unittest.TestCase):

    def test_valid_object(self):
        schema = {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
            },
        }
        result = validate_response({"id": 1, "name": "Alice"}, schema)
        self.assertTrue(result.valid)

    def test_missing_required(self):
        schema = {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}}
        result = validate_response({"name": "x"}, schema)
        self.assertFalse(result.valid)

    def test_type_mismatch(self):
        result = validate_response("oops", {"type": "integer"})
        self.assertFalse(result.valid)

    def test_array_items(self):
        schema = {"type": "array", "items": {"type": "string"}}
        self.assertTrue(validate_response(["a", "b"], schema).valid)
        self.assertFalse(validate_response(["a", 1], schema).valid)

    def test_enum_check(self):
        schema = {"type": "string", "enum": ["red", "green"]}
        self.assertTrue(validate_response("red", schema).valid)
        self.assertFalse(validate_response("blue", schema).valid)

    def test_one_of(self):
        schema = {"oneOf": [{"type": "string"}, {"type": "integer"}]}
        self.assertTrue(validate_response("a", schema).valid)
        self.assertTrue(validate_response(7, schema).valid)
        self.assertFalse(validate_response([], schema).valid)

    def test_additional_properties_false(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "additionalProperties": False,
        }
        self.assertFalse(validate_response({"a": 1, "b": 2}, schema).valid)

    def test_assert_valid_raises(self):
        with self.assertRaises(ContractError):
            assert_valid("x", {"type": "integer"})


class TestOpenApi(unittest.TestCase):

    def setUp(self):
        self.doc = {
            "paths": {
                "/users/{id}": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/User"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                        },
                    }
                }
            },
        }

    def test_resolves_ref(self):
        result = validate_against_openapi(
            {"id": 1, "name": "x"}, self.doc, "/users/{id}", "GET", 200,
        )
        self.assertTrue(result.valid)

    def test_unknown_path_raises(self):
        with self.assertRaises(ContractError):
            validate_against_openapi({}, self.doc, "/nope", "GET", 200)


if __name__ == "__main__":
    unittest.main()
