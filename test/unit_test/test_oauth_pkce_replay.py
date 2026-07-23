"""Unit tests for je_web_runner.utils.oauth_pkce_replay."""
import unittest

from je_web_runner.utils.oauth_pkce_replay.replay import (
    OauthPkceReplayError,
    ReplayCase,
    ReplayOutcome,
    ReplayResult,
    TokenExchangeResponse,
    assert_all_rejected,
    challenge_for,
    generate_verifier,
    replay,
    run_cases,
)


class TestPkceHelpers(unittest.TestCase):

    def test_verifier_length(self):
        v = generate_verifier(length=64)
        self.assertGreaterEqual(len(v), 43)

    def test_verifier_bad_length(self):
        with self.assertRaises(OauthPkceReplayError):
            generate_verifier(length=10)
        with self.assertRaises(OauthPkceReplayError):
            generate_verifier(length=200)

    def test_challenge_deterministic(self):
        c = challenge_for("test_verifier_string")
        self.assertEqual(c, challenge_for("test_verifier_string"))

    def test_challenge_no_padding(self):
        self.assertFalse(challenge_for("x").endswith("="))

    def test_empty_verifier(self):
        with self.assertRaises(OauthPkceReplayError):
            challenge_for("")


class TestReplay(unittest.TestCase):

    def test_rejected_outcome(self):
        def probe(payload):
            return TokenExchangeResponse(
                status_code=400, body={"error": "invalid_grant"},
            )
        result = replay(ReplayCase(name="x", payload={}), probe)
        self.assertEqual(result.outcome, ReplayOutcome.REJECTED)

    def test_accepted_outcome_is_bug(self):
        def probe(payload):
            return TokenExchangeResponse(
                status_code=200,
                body={"access_token": "abc"},  # nosec B105 — fake stubbed token
            )
        result = replay(ReplayCase(name="x", payload={}), probe)
        self.assertEqual(result.outcome, ReplayOutcome.ACCEPTED)

    def test_server_error_ambiguous(self):
        def probe(payload):
            return TokenExchangeResponse(status_code=502, body={})
        result = replay(ReplayCase(name="x", payload={}), probe)
        self.assertEqual(result.outcome, ReplayOutcome.AMBIGUOUS)

    def test_probe_exception(self):
        def boom(p):
            raise RuntimeError("net")
        with self.assertRaises(OauthPkceReplayError):
            replay(ReplayCase(name="x", payload={}), boom)

    def test_rejects_non_case(self):
        with self.assertRaises(OauthPkceReplayError):
            replay("nope", lambda p: TokenExchangeResponse(200, {}))

    def test_non_callable(self):
        with self.assertRaises(OauthPkceReplayError):
            replay(ReplayCase("x", {}), "nope")

    def test_bad_probe_return(self):
        with self.assertRaises(OauthPkceReplayError):
            replay(ReplayCase("x", {}), lambda p: "nope")


class TestRunCases(unittest.TestCase):

    def test_all_rejected(self):
        results = run_cases(
            [ReplayCase("a", {}), ReplayCase("b", {})],
            lambda p: TokenExchangeResponse(400, {"error": "invalid_grant"}),
        )
        self.assertEqual([r.outcome for r in results],
                         [ReplayOutcome.REJECTED, ReplayOutcome.REJECTED])

    def test_empty_cases(self):
        with self.assertRaises(OauthPkceReplayError):
            run_cases([], lambda p: TokenExchangeResponse(400, {}))


class TestAssertRejected(unittest.TestCase):

    def test_pass(self):
        assert_all_rejected([ReplayResult(
            case="x", outcome=ReplayOutcome.REJECTED, status_code=400,
        )])

    def test_fail(self):
        with self.assertRaises(OauthPkceReplayError):
            assert_all_rejected([ReplayResult(
                case="x", outcome=ReplayOutcome.ACCEPTED, status_code=200,
            )])

    def test_empty_results_rejected(self):
        # No results means nothing was tested — must fail, not vacuously pass.
        with self.assertRaises(OauthPkceReplayError):
            assert_all_rejected([])


if __name__ == "__main__":
    unittest.main()
