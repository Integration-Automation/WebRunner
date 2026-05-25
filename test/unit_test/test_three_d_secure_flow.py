"""Unit tests for je_web_runner.utils.three_d_secure_flow."""
import unittest

from je_web_runner.utils.three_d_secure_flow.flow import (
    Flow,
    Outcome,
    ThreeDSecureFlowError,
    TransStatus,
    assert_challenge_branch_complete,
    assert_no_silent_finalize,
    assert_outcome,
    assert_user_message_for,
    classify,
)


class TestClassify(unittest.TestCase):

    def test_frictionless_ok(self):
        f = Flow(trans_status=TransStatus.AUTHENTICATED, order_finalized=True)
        self.assertEqual(classify(f), Outcome.FRICTIONLESS_OK)

    def test_challenge_ok(self):
        f = Flow(trans_status=TransStatus.CHALLENGE,
                 challenge_shown=True, cres_submitted=True,
                 order_finalized=True)
        self.assertEqual(classify(f), Outcome.CHALLENGE_OK)

    def test_rejected(self):
        f = Flow(trans_status=TransStatus.REJECTED, order_finalized=False)
        self.assertEqual(classify(f), Outcome.REJECTED)

    def test_fallback(self):
        f = Flow(trans_status=TransStatus.ATTEMPTED)
        self.assertEqual(classify(f), Outcome.FALLBACK)

    def test_incomplete_frictionless_with_challenge(self):
        f = Flow(trans_status=TransStatus.AUTHENTICATED,
                 challenge_shown=True, order_finalized=True)
        self.assertEqual(classify(f), Outcome.INCOMPLETE)

    def test_incomplete_challenge_no_cres(self):
        f = Flow(trans_status=TransStatus.CHALLENGE,
                 challenge_shown=True, cres_submitted=False)
        self.assertEqual(classify(f), Outcome.INCOMPLETE)

    def test_silent_accept_rejected(self):
        f = Flow(trans_status=TransStatus.REJECTED, order_finalized=True)
        # classify returns INCOMPLETE for finalized-despite-reject
        self.assertEqual(classify(f), Outcome.INCOMPLETE)


class TestInit(unittest.TestCase):

    def test_bad_trans_status(self):
        with self.assertRaises(ThreeDSecureFlowError):
            Flow(trans_status="Y")   # must be enum, not raw str


class TestAssertOutcome(unittest.TestCase):

    def test_pass(self):
        assert_outcome(
            Flow(trans_status=TransStatus.AUTHENTICATED,
                 order_finalized=True),
            expected=Outcome.FRICTIONLESS_OK,
        )

    def test_fail(self):
        with self.assertRaises(ThreeDSecureFlowError):
            assert_outcome(
                Flow(trans_status=TransStatus.AUTHENTICATED),
                expected=Outcome.FRICTIONLESS_OK,
            )

    def test_bad_expected(self):
        with self.assertRaises(ThreeDSecureFlowError):
            assert_outcome(Flow(trans_status=TransStatus.AUTHENTICATED),
                           expected="ok")


class TestSilentFinalize(unittest.TestCase):

    def test_pass(self):
        assert_no_silent_finalize(
            Flow(trans_status=TransStatus.AUTHENTICATED, order_finalized=True),
        )

    def test_fail(self):
        with self.assertRaises(ThreeDSecureFlowError):
            assert_no_silent_finalize(
                Flow(trans_status=TransStatus.REJECTED, order_finalized=True),
            )


class TestChallengeComplete(unittest.TestCase):

    def test_skip_non_challenge(self):
        assert_challenge_branch_complete(
            Flow(trans_status=TransStatus.AUTHENTICATED),
        )

    def test_iframe_missing(self):
        with self.assertRaises(ThreeDSecureFlowError):
            assert_challenge_branch_complete(
                Flow(trans_status=TransStatus.CHALLENGE),
            )

    def test_cres_missing(self):
        with self.assertRaises(ThreeDSecureFlowError):
            assert_challenge_branch_complete(
                Flow(trans_status=TransStatus.CHALLENGE,
                     challenge_shown=True),
            )

    def test_complete(self):
        assert_challenge_branch_complete(
            Flow(trans_status=TransStatus.CHALLENGE,
                 challenge_shown=True, cres_submitted=True),
        )


class TestUserMessage(unittest.TestCase):

    def test_pass(self):
        assert_user_message_for(
            Flow(trans_status=TransStatus.REJECTED,
                 error_displayed="Card was declined by your issuer."),
            contains="declined",
        )

    def test_fail(self):
        with self.assertRaises(ThreeDSecureFlowError):
            assert_user_message_for(
                Flow(trans_status=TransStatus.REJECTED,
                     error_displayed="oops"),
                contains="declined",
            )

    def test_skip_non_reject(self):
        assert_user_message_for(
            Flow(trans_status=TransStatus.AUTHENTICATED,
                 order_finalized=True),
            contains="declined",
        )


if __name__ == "__main__":
    unittest.main()
