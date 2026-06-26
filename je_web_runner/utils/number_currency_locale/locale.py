"""
Number / currency / date locale-format assertion helpers.

Common bugs caught:

* US ``$1,234.56`` ↔ DE ``1.234,56 €`` thousands/decimal swap.
* Hard-coded currency symbol in a Japanese view (``¥1,234`` rendered as
  ``$1,234``).
* Indian lakh grouping ``1,23,456`` regressing to Western ``123,456``.
* RTL Arabic-Indic digits ``١٢٣٤`` stripped.
* ISO ``2026-05-24`` flipped to ``05/24/2026`` in a French view.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from je_web_runner.utils.exception.exceptions import WebRunnerException


class NumberCurrencyLocaleError(WebRunnerException):
    """Raised when a locale-formatting invariant is violated."""


@dataclass(frozen=True)
class NumberRules:
    decimal: str
    thousands: str
    grouping: tuple[int, ...] = (3,)


@dataclass(frozen=True)
class CurrencyRules:
    symbol: str
    code: str
    symbol_position: str = "prefix"     # "prefix" | "suffix"


# Curated minimal locale catalog — extend as you adopt new locales
NUMBER_RULES: dict[str, NumberRules] = {
    "en-US": NumberRules(decimal=".", thousands=","),
    "en-GB": NumberRules(decimal=".", thousands=","),
    "de-DE": NumberRules(decimal=",", thousands="."),
    "fr-FR": NumberRules(decimal=",", thousands=" "),  # NBSP
    "es-ES": NumberRules(decimal=",", thousands="."),
    "ja-JP": NumberRules(decimal=".", thousands=","),
    "zh-CN": NumberRules(decimal=".", thousands=","),
    "hi-IN": NumberRules(decimal=".", thousands=",", grouping=(3, 2)),
    "ar-EG": NumberRules(decimal="٫", thousands="٬"),  # Arabic
}

CURRENCY_RULES: dict[str, CurrencyRules] = {
    "en-US": CurrencyRules(symbol="$", code="USD"),
    "en-GB": CurrencyRules(symbol="£", code="GBP"),
    "de-DE": CurrencyRules(symbol="€", code="EUR", symbol_position="suffix"),
    "fr-FR": CurrencyRules(symbol="€", code="EUR", symbol_position="suffix"),
    "ja-JP": CurrencyRules(symbol="¥", code="JPY"),
    "zh-CN": CurrencyRules(symbol="¥", code="CNY"),
    "hi-IN": CurrencyRules(symbol="₹", code="INR"),
}


def _strip_currency(rendered: str) -> str:
    return re.sub(r"[^\d.,٫٬٠-٩\s-]", "", rendered).strip()


def _detect_decimal(body: str):
    """If both '.' and ',' appear, the LAST one is the decimal.
    If only one appears, treat it as thousands when followed by exactly
    three digits, otherwise as the decimal."""
    last_dot = body.rfind(".")
    last_comma = body.rfind(",")
    if last_dot == -1 and last_comma == -1:
        return None
    if last_dot != -1 and last_comma != -1:
        return "." if last_dot > last_comma else ","
    only = "." if last_dot != -1 else ","
    tail_len = len(body) - body.rfind(only) - 1
    return None if tail_len == 3 else only


def _check_indian_grouping(body: str, rules: NumberRules, rendered: str) -> None:
    if rules.grouping != (3, 2) or rules.thousands not in body:
        return
    integer_part = body.split(rules.decimal, 1)[0]
    groups = integer_part.split(rules.thousands)
    if len(groups) >= 3 and any(len(g) != 2 for g in groups[1:-1]):
        raise NumberCurrencyLocaleError(
            f"{rendered!r} not Indian-grouped (groups={groups})"
        )


def assert_number_format(rendered: str, locale: str) -> None:
    """Verify the number portion of ``rendered`` follows the locale rules."""
    if not isinstance(rendered, str) or not rendered.strip():
        raise NumberCurrencyLocaleError("rendered must be non-empty string")
    rules = NUMBER_RULES.get(locale)
    if rules is None:
        raise NumberCurrencyLocaleError(f"unknown locale: {locale!r}")
    body = _strip_currency(rendered)
    if not body:
        raise NumberCurrencyLocaleError(
            f"no numeric content found in {rendered!r}"
        )
    decimal_sep = _detect_decimal(body)
    if decimal_sep is not None and decimal_sep != rules.decimal:
        raise NumberCurrencyLocaleError(
            f"{rendered!r} uses {decimal_sep!r} as decimal — "
            f"expected {rules.decimal!r} for {locale}"
        )
    _check_indian_grouping(body, rules, rendered)


def assert_currency_symbol(rendered: str, locale: str) -> None:
    rules = CURRENCY_RULES.get(locale)
    if rules is None:
        raise NumberCurrencyLocaleError(
            f"no currency rule for locale {locale!r}"
        )
    if rules.symbol not in rendered:
        raise NumberCurrencyLocaleError(
            f"{rendered!r} missing currency symbol {rules.symbol!r} "
            f"({rules.code}) for {locale}"
        )
    stripped = rendered.replace(rules.symbol, "").strip()
    if rules.symbol_position == "prefix" and rendered.lstrip().startswith(stripped):
        raise NumberCurrencyLocaleError(
            f"{rendered!r}: symbol {rules.symbol!r} not in prefix position"
        )
    if rules.symbol_position == "suffix" and rendered.rstrip().endswith(rules.symbol) is False:
        raise NumberCurrencyLocaleError(
            f"{rendered!r}: symbol {rules.symbol!r} not in suffix position"
        )


_DATE_PATTERNS = {
    "iso": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "us": re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$"),
    "eu": re.compile(r"^\d{1,2}\.\d{1,2}\.\d{2,4}$"),
    "fr": re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$"),
}


def assert_date_format(rendered: str, fmt: str) -> None:
    if fmt not in _DATE_PATTERNS:
        raise NumberCurrencyLocaleError(
            f"unknown date format {fmt!r}; choose one of {list(_DATE_PATTERNS)}"
        )
    if not _DATE_PATTERNS[fmt].match(rendered.strip()):
        raise NumberCurrencyLocaleError(
            f"{rendered!r} does not match {fmt} date pattern"
        )
