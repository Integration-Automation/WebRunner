"""Unit tests for je_web_runner.utils.number_currency_locale."""
import unittest

from je_web_runner.utils.number_currency_locale.locale import (
    NumberCurrencyLocaleError,
    assert_currency_symbol,
    assert_date_format,
    assert_number_format,
)


class TestNumber(unittest.TestCase):

    def test_us(self):
        assert_number_format("1,234.56", "en-US")

    def test_de(self):
        assert_number_format("1.234,56", "de-DE")

    def test_us_in_de_raises(self):
        with self.assertRaises(NumberCurrencyLocaleError):
            assert_number_format("1,234.56", "de-DE")

    def test_indian(self):
        assert_number_format("1,23,456.78", "hi-IN")

    def test_indian_wrong_grouping(self):
        with self.assertRaises(NumberCurrencyLocaleError):
            assert_number_format("1,234,567.00", "hi-IN")

    def test_unknown_locale(self):
        with self.assertRaises(NumberCurrencyLocaleError):
            assert_number_format("1,234", "xx-YY")

    def test_empty(self):
        with self.assertRaises(NumberCurrencyLocaleError):
            assert_number_format("", "en-US")

    def test_no_numbers(self):
        with self.assertRaises(NumberCurrencyLocaleError):
            assert_number_format("abc", "en-US")


class TestCurrency(unittest.TestCase):

    def test_us_dollar(self):
        assert_currency_symbol("$1,234.56", "en-US")

    def test_de_euro_suffix(self):
        assert_currency_symbol("1.234,56 €", "de-DE")

    def test_missing_symbol(self):
        with self.assertRaises(NumberCurrencyLocaleError):
            assert_currency_symbol("1,234.56", "en-US")

    def test_unknown_locale(self):
        with self.assertRaises(NumberCurrencyLocaleError):
            assert_currency_symbol("1,234", "xx-YY")


class TestDate(unittest.TestCase):

    def test_iso(self):
        assert_date_format("2026-05-24", "iso")

    def test_us(self):
        assert_date_format("5/24/2026", "us")

    def test_eu(self):
        assert_date_format("24.5.2026", "eu")

    def test_iso_against_us_fails(self):
        with self.assertRaises(NumberCurrencyLocaleError):
            assert_date_format("2026-05-24", "us")

    def test_unknown_format(self):
        with self.assertRaises(NumberCurrencyLocaleError):
            assert_date_format("x", "weird")


if __name__ == "__main__":
    unittest.main()
