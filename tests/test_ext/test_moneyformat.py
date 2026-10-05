from decimal import Decimal

import pytest

from api.ext.moneyformat import currency_table


@pytest.mark.parametrize(
    ("currency", "rate", "expected"),
    [
        ("USD", "50000.123", "50000.12"),
        ("USD", "5.12", "5.12"),
        ("USD", "0.5", "0.50"),
        ("USD", "0.123456", "0.123"),
        ("USD", "0.004", "0.004"),
        ("USD", "0.004123", "0.00412"),
        ("USD", "0.0099999", "0.01"),
        ("USD", "0.0000123456", "0.0000123"),
        ("USD", "0", "0.00"),
        ("JPY", "5", "5"),
        ("JPY", "5.123", "5.12"),
        ("JPY", "99.5", "99.5"),
        ("JPY", "5123.4", "5123"),
    ],
)
def test_rate_divisibility(currency: str, rate: str, expected: str) -> None:
    value = Decimal(rate)
    divisibility = currency_table.get_rate_divisibility(currency, value)
    assert currency_table.format_decimal(currency, value, divisibility=divisibility) == expected
