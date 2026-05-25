"""Unit tests for je_web_runner.utils.cors_matrix."""
import unittest

from je_web_runner.utils.cors_matrix.matrix import (
    CorsCase,
    CorsMatrixError,
    CorsOutcome,
    CorsResponse,
    CorsResult,
    assert_credentials_require_explicit_origin,
    assert_origin_blocked,
    build_matrix,
    classify,
    run_matrix,
)


class TestBuildMatrix(unittest.TestCase):

    def test_default(self):
        cases = build_matrix()
        # 6 verbs * 3 origins * 2 creds = 36
        self.assertEqual(len(cases), 36)

    def test_empty_axes_rejected(self):
        with self.assertRaises(CorsMatrixError):
            build_matrix(verbs=[])
        with self.assertRaises(CorsMatrixError):
            build_matrix(origins=[])
        with self.assertRaises(CorsMatrixError):
            build_matrix(credentials_modes=[])


class TestClassify(unittest.TestCase):

    def test_simple_allowed(self):
        case = CorsCase(verb="GET", origin="https://a", with_credentials=False)
        resp = CorsResponse(status_code=200, allow_origin="https://a")
        result = classify(case, resp)
        self.assertEqual(result.outcome, CorsOutcome.ALLOWED)

    def test_wildcard_allowed_no_creds(self):
        case = CorsCase(verb="GET", origin="https://a", with_credentials=False)
        result = classify(case, CorsResponse(status_code=200, allow_origin="*"))
        self.assertEqual(result.outcome, CorsOutcome.ALLOWED)

    def test_wildcard_blocked_with_creds(self):
        case = CorsCase(verb="GET", origin="https://a", with_credentials=True)
        result = classify(case, CorsResponse(
            status_code=200, allow_origin="*", allow_credentials=True,
        ))
        self.assertEqual(result.outcome, CorsOutcome.BLOCKED)
        self.assertIn("incompatible", result.note)

    def test_creds_missing_credentials_header(self):
        case = CorsCase(verb="GET", origin="https://a", with_credentials=True)
        result = classify(case, CorsResponse(
            status_code=200, allow_origin="https://a", allow_credentials=False,
        ))
        self.assertEqual(result.outcome, CorsOutcome.BLOCKED)
        self.assertIn("Credentials", result.note)

    def test_origin_mismatch(self):
        case = CorsCase(verb="GET", origin="https://evil", with_credentials=False)
        result = classify(case, CorsResponse(
            status_code=200, allow_origin="https://trusted",
        ))
        self.assertEqual(result.outcome, CorsOutcome.BLOCKED)

    def test_preflight_missing_method(self):
        case = CorsCase(verb="DELETE", origin="https://a", with_credentials=False)
        result = classify(case, CorsResponse(
            status_code=204, allow_origin="https://a", allow_methods=("GET",),
        ))
        self.assertEqual(result.outcome, CorsOutcome.BLOCKED)
        self.assertIn("ACA-Methods", result.note)

    def test_preflight_method_present(self):
        case = CorsCase(verb="DELETE", origin="https://a", with_credentials=False)
        result = classify(case, CorsResponse(
            status_code=204, allow_origin="https://a", allow_methods=("DELETE",),
        ))
        self.assertEqual(result.outcome, CorsOutcome.ALLOWED)

    def test_server_error_ambiguous(self):
        result = classify(
            CorsCase(verb="GET", origin="https://a", with_credentials=False),
            CorsResponse(status_code=500, allow_origin=None),
        )
        self.assertEqual(result.outcome, CorsOutcome.AMBIGUOUS)

    def test_origin_null(self):
        case = CorsCase(verb="GET", origin="null", with_credentials=False)
        result = classify(case, CorsResponse(
            status_code=200, allow_origin="null",
        ))
        self.assertEqual(result.outcome, CorsOutcome.ALLOWED)

    def test_rejects_non_response(self):
        with self.assertRaises(CorsMatrixError):
            classify(CorsCase("GET", "x", False), "nope")


class TestRunMatrix(unittest.TestCase):

    def test_runs_all(self):
        def fake(case):
            return CorsResponse(status_code=200, allow_origin=case.origin,
                                allow_credentials=case.with_credentials,
                                allow_methods=("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"))
        results = run_matrix(build_matrix(), fake)
        self.assertGreater(len(results), 0)

    def test_empty_cases(self):
        with self.assertRaises(CorsMatrixError):
            run_matrix([], lambda c: CorsResponse(200, "*"))

    def test_non_callable(self):
        with self.assertRaises(CorsMatrixError):
            run_matrix([CorsCase("GET", "x", False)], "nope")

    def test_probe_failure(self):
        def boom(_c):
            raise RuntimeError("net")
        with self.assertRaises(CorsMatrixError):
            run_matrix([CorsCase("GET", "x", False)], boom)


class TestAssertions(unittest.TestCase):

    def test_origin_blocked_pass(self):
        results = [CorsResult(
            case=CorsCase("GET", "https://evil", False),
            outcome=CorsOutcome.BLOCKED,
            response=CorsResponse(200, None),
        )]
        assert_origin_blocked(results, origin="https://evil")

    def test_origin_blocked_fail(self):
        results = [CorsResult(
            case=CorsCase("GET", "https://evil", False),
            outcome=CorsOutcome.ALLOWED,
            response=CorsResponse(200, "https://evil"),
        )]
        with self.assertRaises(CorsMatrixError):
            assert_origin_blocked(results, origin="https://evil")

    def test_credentials_explicit_pass(self):
        results = [CorsResult(
            case=CorsCase("GET", "https://a", True),
            outcome=CorsOutcome.ALLOWED,
            response=CorsResponse(200, "https://a", allow_credentials=True),
        )]
        assert_credentials_require_explicit_origin(results)

    def test_credentials_wildcard_fail(self):
        results = [CorsResult(
            case=CorsCase("GET", "https://a", True),
            outcome=CorsOutcome.BLOCKED,
            response=CorsResponse(200, "*", allow_credentials=True),
        )]
        with self.assertRaises(CorsMatrixError):
            assert_credentials_require_explicit_origin(results)


if __name__ == "__main__":
    unittest.main()
