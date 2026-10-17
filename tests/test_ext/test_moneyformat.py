from decimal import Decimal

import pytest

from api.ext.moneyformat import currency_table, format_raw, round_half_up


@pytest.mark.parametrize(
    ("currency", "value", "divisibility", "expected"),
    [
        ("BTC", "0.000333333333", None, "0.00033334"),
        ("BTC", "0.1", None, "0.10000000"),
        ("USD", "0.333", 2, "0.34"),
        ("JPY", "100.2", None, "101"),
        ("BTC", "5", 0, "5"),
    ],
)
def test_round_up(currency: str, value: str, divisibility: int | None, expected: str) -> None:
    assert str(currency_table.round_up(currency, Decimal(value), divisibility=divisibility)) == expected


@pytest.mark.parametrize(
    ("value", "precision", "expected"), [("1234.4", 0, "1234"), ("1234.5", 0, "1235"), ("1.005", 2, "1.01")]
)
def test_round_half_up(value: str, precision: int, expected: str) -> None:
    assert str(round_half_up(Decimal(value), precision)) == expected


@pytest.mark.parametrize(
    ("currency", "value", "divisibility", "rounded", "formatted"),
    [
        ("JPY", "1234.6", None, "1235", "1235"),
        ("SATS", "1000.4", None, "1000", "1000"),
        ("BTC", "5.6", 0, "6", "6"),
    ],
)
def test_zero_divisibility(currency: str, value: str, divisibility: int | None, rounded: str, formatted: str) -> None:
    assert str(currency_table.round_half_up(currency, Decimal(value), divisibility=divisibility)) == rounded
    assert currency_table.format_decimal(currency, Decimal(value), divisibility=divisibility) == formatted


@pytest.mark.parametrize(
    ("value", "divisibility", "expected"),
    [("9.9999", 2, "9.99"), ("10.0002", 2, "10.00"), ("0.00033333", 8, "0.00033333"), ("1000.9", 0, "1000")],
)
def test_round_down(value: str, divisibility: int, expected: str) -> None:
    assert str(currency_table.round_down("USD", Decimal(value), divisibility=divisibility)) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("50000.000000000000000000", "50000"),
        ("1.020000000000000000000000000000000000", "1.02"),
        ("0.99999999999999999999", "1"),
        ("4123456789012.345678901234567891", "4123456789012.345678901234567891"),
        ("0", "0"),
    ],
)
def test_format_raw(value: str, expected: str) -> None:
    assert format_raw(Decimal(value)) == expected


def test_format_decimal_rounds_half_up() -> None:
    assert currency_table.format_decimal("USD", Decimal("1.005")) == "1.01"
