"""Unit tests for je_web_runner.utils.idempotency_check."""
import unittest

from je_web_runner.utils.idempotency_check.check import (
    IdemResponse,
    IdempotencyCheckError,
    IdempotencyReport,
    assert_idempotent,
    check,
    generate_idempotency_key,
)


class _StateBox:
    def __init__(self):
        self.value = 0


def _idempotent_runner(state):
    def _run():
        if state.value == 0:
            state.value = 1
        return IdemResponse(status_code=200, body={"id": 42, "ok": True},
                            side_effect_count=state.value)
    return _run


def _non_idempotent_runner(state):
    def _run():
        state.value += 1
        return IdemResponse(status_code=200, body={"id": state.value},
                            side_effect_count=state.value)
    return _run


class TestCheck(unittest.TestCase):

    def test_idempotent_passes(self):
        state = _StateBox()
        report = check(_idempotent_runner(state), state_probe=lambda: state.value)
        self.assertTrue(report.passed())

    def test_non_idempotent_caught(self):
        state = _StateBox()
        report = check(_non_idempotent_runner(state))
        self.assertFalse(report.passed())
        joined = "; ".join(report.violations)
        self.assertIn("body differs", joined)

    def test_status_change_caught(self):
        calls = [
            IdemResponse(200, {"id": 1}),
            IdemResponse(409, {"id": 1}),
        ]
        def runner():
            return calls.pop(0)
        report = check(runner)
        self.assertFalse(report.passed())

    def test_status_change_allowed(self):
        calls = [
            IdemResponse(200, {"id": 1}),
            IdemResponse(409, {"id": 1}),
        ]
        def runner():
            return calls.pop(0)
        report = check(runner, allow_status_change_to=[409])
        self.assertTrue(report.passed())

    def test_ignore_body_keys(self):
        calls = [
            IdemResponse(200, {"id": 1, "ts": "2026-01-01"}),
            IdemResponse(200, {"id": 1, "ts": "2026-01-02"}),
        ]
        def runner():
            return calls.pop(0)
        report = check(runner, ignore_body_keys=["ts"])
        self.assertTrue(report.passed())

    def test_state_diff_caught(self):
        state = _StateBox()
        def runner():
            state.value += 1
            return IdemResponse(200, {"id": 1})
        report = check(runner, state_probe=lambda: state.value)
        self.assertFalse(report.passed())
        self.assertTrue(any("state changed" in v for v in report.violations))

    def test_side_effect_count_diff(self):
        responses = [
            IdemResponse(200, {"id": 1}, side_effect_count=1),
            IdemResponse(200, {"id": 1}, side_effect_count=2),
        ]
        def runner():
            return responses.pop(0)
        report = check(runner)
        self.assertFalse(report.passed())

    def test_runner_must_be_callable(self):
        with self.assertRaises(IdempotencyCheckError):
            check("not callable")  # type: ignore[arg-type]

    def test_state_probe_must_be_callable(self):
        with self.assertRaises(IdempotencyCheckError):
            check(lambda: IdemResponse(200, {}), state_probe="x")  # type: ignore[arg-type]

    def test_runner_must_return_idem_response(self):
        with self.assertRaises(IdempotencyCheckError):
            check(lambda: "nope")

    def test_runner_exception_wrapped(self):
        def boom():
            raise RuntimeError("net")
        with self.assertRaises(IdempotencyCheckError):
            check(boom)


class TestAssertIdempotent(unittest.TestCase):

    def test_pass(self):
        report = IdempotencyReport(
            first=IdemResponse(200, {}), second=IdemResponse(200, {}),
        )
        assert_idempotent(report)

    def test_fail(self):
        report = IdempotencyReport(
            first=IdemResponse(200, {}), second=IdemResponse(200, {}),
            violations=["x"],
        )
        with self.assertRaises(IdempotencyCheckError):
            assert_idempotent(report)

    def test_rejects_non_report(self):
        with self.assertRaises(IdempotencyCheckError):
            assert_idempotent("nope")  # type: ignore[arg-type]


class TestKeyGen(unittest.TestCase):

    def test_stable(self):
        self.assertEqual(
            generate_idempotency_key("user", 42),
            generate_idempotency_key("user", 42),
        )

    def test_changes_with_parts(self):
        self.assertNotEqual(
            generate_idempotency_key("user", 42),
            generate_idempotency_key("user", 43),
        )


class TestIdemResponse(unittest.TestCase):

    def test_body_hash_stable(self):
        a = IdemResponse(200, {"id": 1, "x": 2})
        b = IdemResponse(200, {"x": 2, "id": 1})  # different dict key order
        self.assertEqual(a.body_hash(), b.body_hash())


if __name__ == "__main__":
    unittest.main()
