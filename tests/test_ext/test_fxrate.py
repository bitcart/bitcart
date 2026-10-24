import time
from decimal import Decimal
from typing import Any, cast

import pytest

from api.ext import fxrate

pytestmark = pytest.mark.anyio


class StubExchangeRateService:
    default_rules = ""

    async def get_rate(self, exchange: str) -> dict[str, Decimal]:
        return {"BTC_USD": Decimal(50000)}


async def calculate(rules: str) -> tuple[Decimal, fxrate.ExchangePair | None]:
    return await fxrate.calculate_rules(cast(Any, StubExchangeRateService()), rules, "BTC", "USD")


async def test_calculate_rules_reuses_nested_pairs() -> None:
    rate, pair = await calculate("BTC_USD = A_B + A_B\nA_B = C_D + C_D\nC_D = coingecko(BTC_USD)")
    assert rate == Decimal(200000)
    assert str(pair) == "BTC_USD"


async def test_calculate_rules_self_reference_is_bounded() -> None:
    terms = " + ".join(["Q_Q"] * 10)
    start = time.monotonic()
    rate, _ = await calculate(f"BTC_USD = {terms}\nQ_Q = {terms}")
    assert rate.is_nan()
    assert time.monotonic() - start < 1
