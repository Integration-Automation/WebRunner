"""Facade: HTTP, auth, GraphQL, gRPC and API-contract testing, HAR tools."""
from je_web_runner.utils.api.http_client import (
    HttpAssertionError, http_request, http_get, http_post, http_put, http_patch, http_delete, get_last_response,
    http_assert_status, http_assert_json_contains, reset_state,
)
from je_web_runner.utils.api_version_compat.compat import (
    ApiVersionCompatError, FieldSpec, ApiContract, assert_response_compatible, assert_request_compatible,
    CompatMatrixRow, matrix_summary, assert_full_matrix_passes,
)
from je_web_runner.utils.auth.oauth import (
    OAuthError, client_credentials_token, password_grant_token, refresh_token_grant, get_cached_token,
    clear_token_cache, bearer_header,
)
from je_web_runner.utils.graphql_n_plus_1.detect import (
    GraphqlNPlus1Error, Severity, QueryRow, Finding, parse_rows, detect, detect_cartesian, assert_no_n_plus_1,
    report_markdown,
)
from je_web_runner.utils.grpc_streaming_assert.assertions import (
    GrpcStreamingAssertError, Mode, StatusCode, StreamFrame, StreamRecord, parse_record, assert_status,
    assert_frame_count_between, assert_max_frame_size, assert_frames_in_order, assert_no_deadline_exceeded,
    assert_half_close_before_final,
)
from je_web_runner.utils.grpc_tester.client import (
    GrpcTesterError, GrpcStatus, GrpcCall, GrpcCallRecorder, call, encode_grpc_web_message,
    decode_grpc_web_message, parse_trailer, assert_call_ok, assert_call_fails, assert_called,
)
from je_web_runner.utils.har_diff.har_diff import (
    HarDiffError, diff_har, diff_har_files,
)
from je_web_runner.utils.har_to_openapi.converter import (
    HarToOpenapiError, convert, assert_spec_minimum_coverage,
)
from je_web_runner.utils.idempotency_check.check import (
    IdempotencyCheckError, IdemResponse, IdempotencyReport, check, assert_idempotent, generate_idempotency_key,
)
from je_web_runner.utils.openapi_drift.drift import (
    OpenapiDriftError, ApiObservation, DriftReport, diff, assert_no_undocumented, assert_no_zombies,
)
from je_web_runner.utils.openapi_to_e2e.generator import (
    OpenAPIGeneratorError, GeneratedTest, GenerationResult, load_spec, synthesize_example,
    generate_tests_from_spec, generate_tests_from_file, write_tests_to_dir,
)
from je_web_runner.utils.pagination_audit.audit import (
    PaginationAuditError, Page, PageFetcher, PaginationFindings, walk_all_pages, assert_no_duplicates,
    assert_no_cursor_loop, assert_terminated, assert_expected_total, assert_clean, assert_sorted_by,
)
from je_web_runner.utils.rate_limit_assert.rate import (
    RateLimitAssertError, RateLimitResponse, assert_429_after_burst, assert_retry_after_present,
    assert_remaining_monotonic, assert_recovery_after_retry_after,
)

__all__ = [
    "HttpAssertionError", "http_request", "http_get", "http_post", "http_put", "http_patch", "http_delete",
    "get_last_response", "http_assert_status", "http_assert_json_contains", "reset_state", "ApiVersionCompatError",
    "FieldSpec", "ApiContract", "assert_response_compatible", "assert_request_compatible", "CompatMatrixRow",
    "matrix_summary", "assert_full_matrix_passes", "OAuthError", "client_credentials_token",
    "password_grant_token", "refresh_token_grant", "get_cached_token", "clear_token_cache", "bearer_header",
    "GraphqlNPlus1Error", "Severity", "QueryRow", "Finding", "parse_rows", "detect", "detect_cartesian",
    "assert_no_n_plus_1", "report_markdown", "GrpcStreamingAssertError", "Mode", "StatusCode", "StreamFrame",
    "StreamRecord", "parse_record", "assert_status", "assert_frame_count_between", "assert_max_frame_size",
    "assert_frames_in_order", "assert_no_deadline_exceeded", "assert_half_close_before_final", "GrpcTesterError",
    "GrpcStatus", "GrpcCall", "GrpcCallRecorder", "call", "encode_grpc_web_message", "decode_grpc_web_message",
    "parse_trailer", "assert_call_ok", "assert_call_fails", "assert_called", "HarDiffError", "diff_har",
    "diff_har_files", "HarToOpenapiError", "convert", "assert_spec_minimum_coverage", "IdempotencyCheckError",
    "IdemResponse", "IdempotencyReport", "check", "assert_idempotent", "generate_idempotency_key",
    "OpenapiDriftError", "ApiObservation", "DriftReport", "diff", "assert_no_undocumented", "assert_no_zombies",
    "OpenAPIGeneratorError", "GeneratedTest", "GenerationResult", "load_spec", "synthesize_example",
    "generate_tests_from_spec", "generate_tests_from_file", "write_tests_to_dir", "PaginationAuditError", "Page",
    "PageFetcher", "PaginationFindings", "walk_all_pages", "assert_no_duplicates", "assert_no_cursor_loop",
    "assert_terminated", "assert_expected_total", "assert_clean", "assert_sorted_by", "RateLimitAssertError",
    "RateLimitResponse", "assert_429_after_burst", "assert_retry_after_present", "assert_remaining_monotonic",
    "assert_recovery_after_retry_after",
]
