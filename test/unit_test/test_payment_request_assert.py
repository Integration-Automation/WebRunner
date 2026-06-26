"""Unit tests for je_web_runner.utils.payment_request_assert."""
import unittest

from je_web_runner.utils.payment_request_assert.payment import (
    CompletedPayment,
    ConstructedPaymentRequest,
    INSTALL_SCRIPT,
    PaymentLog,
    PaymentRequestAssertError,
    assert_completed,
    assert_shipping_required,
    assert_supports,
    assert_total_currency,
    parse_log,
)


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("PaymentRequest", INSTALL_SCRIPT)
        self.assertIn("__wr_payment__", INSTALL_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        log = parse_log({
            "constructed": [{"methodData": [{"supportedMethods": "basic-card"}],
                             "details": {}, "options": {}}],
            "completed": [{"status": "success"}],
        })
        self.assertEqual(len(log.constructed), 1)

    def test_bad(self):
        with self.assertRaises(PaymentRequestAssertError):
            parse_log("nope")

    def test_skip_non_dict(self):
        log = parse_log({"constructed": ["x"], "completed": ["y"]})
        self.assertEqual(len(log.constructed), 0)


class TestSupports(unittest.TestCase):

    def test_pass(self):
        assert_supports(
            PaymentLog(constructed=[ConstructedPaymentRequest(
                method_data=[{"supportedMethods": "https://apple.com/apple-pay"}],
            )]),
            method="https://apple.com/apple-pay",
        )

    def test_fail(self):
        with self.assertRaises(PaymentRequestAssertError):
            assert_supports(
                PaymentLog(constructed=[ConstructedPaymentRequest(
                    method_data=[{"supportedMethods": "basic-card"}],
                )]),
                method="https://google.com/pay",
            )

    def test_no_pr(self):
        with self.assertRaises(PaymentRequestAssertError):
            assert_supports(PaymentLog(), method="x")

    def test_empty_method(self):
        with self.assertRaises(PaymentRequestAssertError):
            assert_supports(PaymentLog(), method="")


class TestCurrency(unittest.TestCase):

    def test_pass(self):
        assert_total_currency(
            PaymentLog(constructed=[ConstructedPaymentRequest(
                details={"total": {"amount": {"currency": "USD", "value": "10"}}},
            )]),
            currency="USD",
        )

    def test_fail(self):
        with self.assertRaises(PaymentRequestAssertError):
            assert_total_currency(
                PaymentLog(constructed=[ConstructedPaymentRequest(
                    details={"total": {"amount": {"currency": "EUR", "value": "10"}}},
                )]),
                currency="USD",
            )

    def test_empty(self):
        with self.assertRaises(PaymentRequestAssertError):
            assert_total_currency(PaymentLog(), currency="")

    def test_no_pr_constructed(self):
        # No PaymentRequest built → must fail, not vacuously pass (matches
        # assert_supports / assert_completed which both guard empty logs).
        with self.assertRaises(PaymentRequestAssertError):
            assert_total_currency(PaymentLog(), currency="USD")


class TestCompleted(unittest.TestCase):

    def test_pass(self):
        assert_completed(PaymentLog(completed=[CompletedPayment(status="success")]))

    def test_fail_status(self):
        with self.assertRaises(PaymentRequestAssertError):
            assert_completed(PaymentLog(completed=[CompletedPayment(status="fail")]))

    def test_never_completed(self):
        with self.assertRaises(PaymentRequestAssertError):
            assert_completed(PaymentLog())

    def test_bad_status(self):
        with self.assertRaises(PaymentRequestAssertError):
            assert_completed(PaymentLog(), status="weird")


class TestShipping(unittest.TestCase):

    def test_pass(self):
        assert_shipping_required(PaymentLog(constructed=[
            ConstructedPaymentRequest(options={"requestShipping": True}),
        ]))

    def test_fail(self):
        with self.assertRaises(PaymentRequestAssertError):
            assert_shipping_required(PaymentLog(constructed=[
                ConstructedPaymentRequest(options={}),
            ]))


if __name__ == "__main__":
    unittest.main()
