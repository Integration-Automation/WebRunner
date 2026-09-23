"""Unit tests for je_web_runner.utils.rate_limit_assert."""
import unittest

from je_web_runner.utils.rate_limit_assert.rate import (
    RateLimitAssertError,
    RateLimitResponse,
    assert_429_after_burst,
    assert_recovery_after_retry_after,
    assert_remaining_monotonic,
    assert_retry_after_present,
)


def _ok(remaining=None):
    headers = {}
    if remaining is not None:
        headers["X-RateLimit-Remaining"] = str(remaining)
    return RateLimitResponse(status_code=200, headers=headers)


def _too_many(retry_after="1"):
    return RateLimitResponse(status_code=429,
                             headers={"Retry-After": retry_after})


class TestParseAccessors(unittest.TestCase):

    def test_retry_after(self):
        self.assertEqual(_too_many("2").retry_after_seconds, 2)

    def test_bad_retry_after(self):
        r = RateLimitResponse(status_code=429,
                              headers={"Retry-After": "soon"})
        self.assertIsNone(r.retry_after_seconds)

    def test_remaining(self):
        self.assertEqual(_ok(5).remaining, 5)


class TestBurst(unittest.TestCase):

    def test_pass(self):
        responses = [_ok()] * 5 + [_too_many()]
        r = assert_429_after_burst(responses, after=5)
        self.assertTrue(r.is_429)

    def test_no_429(self):
        value = [_ok()] * 6
        with self.assertRaises(RateLimitAssertError):
            assert_429_after_burst(value, after=5)

    def test_too_few(self):
        oks = [_ok()]
        with self.assertRaises(RateLimitAssertError):
            assert_429_after_burst(oks, after=5)

    def test_bad_after(self):
        with self.assertRaises(RateLimitAssertError):
            assert_429_after_burst([], after=0)


class TestRetryAfter(unittest.TestCase):

    def test_pass(self):
        assert_retry_after_present(_too_many("2"))

    def test_non_429(self):
        ok = _ok()
        with self.assertRaises(RateLimitAssertError):
            assert_retry_after_present(ok)

    def test_missing(self):
        rate_limit_response = RateLimitResponse(status_code=429)
        with self.assertRaises(RateLimitAssertError):
            assert_retry_after_present(rate_limit_response)

    def test_zero(self):
        too_many = _too_many("0")
        with self.assertRaises(RateLimitAssertError):
            assert_retry_after_present(too_many)


class TestMonotonic(unittest.TestCase):

    def test_pass(self):
        assert_remaining_monotonic([_ok(5), _ok(4), _ok(3)])

    def test_fail(self):
        oks = [_ok(5), _ok(10)]
        with self.assertRaises(RateLimitAssertError):
            assert_remaining_monotonic(oks)

    def test_skip_no_header(self):
        assert_remaining_monotonic([_ok(), _ok()])


class TestRecovery(unittest.TestCase):

    def test_pass(self):
        assert_recovery_after_retry_after(before=_too_many(), after=_ok())

    def test_fail(self):
        before_value = _too_many()
        after_value = _too_many()
        with self.assertRaises(RateLimitAssertError):
            assert_recovery_after_retry_after(
                before=before_value, after=after_value,
            )

    def test_before_not_429(self):
        before_value = _ok()
        after_value = _ok()
        with self.assertRaises(RateLimitAssertError):
            assert_recovery_after_retry_after(before=before_value, after=after_value)


if __name__ == "__main__":
    unittest.main()
