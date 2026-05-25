"""Unit tests for je_web_runner.utils.api_version_compat."""
import unittest

from je_web_runner.utils.api_version_compat.compat import (
    ApiContract,
    ApiVersionCompatError,
    CompatMatrixRow,
    FieldSpec,
    assert_full_matrix_passes,
    assert_request_compatible,
    assert_response_compatible,
    matrix_summary,
)


CONTRACT = ApiContract(
    endpoint="/users/{id}",
    response_fields=[
        FieldSpec(name="id", type="integer"),
        FieldSpec(name="name", type="string"),
        FieldSpec(name="bio", type="string", required=False),
    ],
    request_fields=[
        FieldSpec(name="name", type="string"),
    ],
)


class TestResponse(unittest.TestCase):

    def test_pass(self):
        assert_response_compatible(
            CONTRACT, {"id": 1, "name": "alice"},
        )

    def test_missing_required(self):
        with self.assertRaises(ApiVersionCompatError):
            assert_response_compatible(CONTRACT, {"id": 1})

    def test_wrong_type(self):
        with self.assertRaises(ApiVersionCompatError):
            assert_response_compatible(CONTRACT, {"id": "abc", "name": "x"})

    def test_optional_missing_ok(self):
        assert_response_compatible(CONTRACT, {"id": 1, "name": "x"})

    def test_bad_contract(self):
        with self.assertRaises(ApiVersionCompatError):
            assert_response_compatible("nope", {})

    def test_bad_response(self):
        with self.assertRaises(ApiVersionCompatError):
            assert_response_compatible(CONTRACT, "nope")


class TestRequest(unittest.TestCase):

    def test_pass(self):
        assert_request_compatible(CONTRACT, server_required_fields=["name"])

    def test_surprise(self):
        with self.assertRaises(ApiVersionCompatError):
            assert_request_compatible(
                CONTRACT, server_required_fields=["name", "captcha"],
            )

    def test_bad_contract(self):
        with self.assertRaises(ApiVersionCompatError):
            assert_request_compatible("nope", server_required_fields=[])


class TestMatrix(unittest.TestCase):

    def test_summary(self):
        summary = matrix_summary([
            CompatMatrixRow(client_version="v1", server_version="v2",
                            passed=True),
        ])
        self.assertEqual(summary[0]["client"], "v1")

    def test_assert_pass(self):
        assert_full_matrix_passes([
            CompatMatrixRow(client_version="v1", server_version="v1",
                            passed=True),
        ])

    def test_assert_fail(self):
        with self.assertRaises(ApiVersionCompatError):
            assert_full_matrix_passes([
                CompatMatrixRow(client_version="v1", server_version="v2",
                                passed=False),
            ])


if __name__ == "__main__":
    unittest.main()
