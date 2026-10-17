import json
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Context, Decimal

RAW_PRECISION = 18  # max number of decimals any crypto we support has
RAW_CONTEXT = Context(prec=60, rounding=ROUND_HALF_UP)


def round_half_up(value: Decimal, precision: int) -> Decimal:
    return value.quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP)


def round_up(value: Decimal, precision: int) -> Decimal:
    return value.quantize(Decimal(10) ** -precision, rounding=ROUND_CEILING)


def round_down(value: Decimal, precision: int) -> Decimal:
    return value.quantize(Decimal(10) ** -precision, rounding=ROUND_FLOOR)


def to_raw(value: Decimal) -> Decimal:
    return RAW_CONTEXT.quantize(value, Decimal(10) ** -RAW_PRECISION)


def format_raw(value: Decimal) -> str:
    return f"{to_raw(value).normalize(RAW_CONTEXT):f}"


DEFAULT_DIVISIBILITY = 2


class CurrencyTable:
    def __init__(self) -> None:
        with open("api/ext/moneyformat/currencies.json") as f:
            self.divisibilities: dict[str, int] = json.load(f)

    def get_divisibility(self, currency: str, divisibility: int | None = None) -> int:
        if divisibility is not None:
            return divisibility
        return self.divisibilities.get(currency.upper(), DEFAULT_DIVISIBILITY)

    def round_half_up(self, currency: str, value: Decimal, divisibility: int | None = None) -> Decimal:
        return round_half_up(value, self.get_divisibility(currency, divisibility))

    def round_up(self, currency: str, value: Decimal, divisibility: int | None = None) -> Decimal:
        return round_up(value, self.get_divisibility(currency, divisibility))

    def round_down(self, currency: str, value: Decimal, divisibility: int | None = None) -> Decimal:
        return round_down(value, self.get_divisibility(currency, divisibility))

    def format_decimal(self, currency: str, value: Decimal, divisibility: int | None = None) -> str:
        if isinstance(value, str):
            value = Decimal(value)
        return f"{self.round_half_up(currency, value, divisibility=divisibility):f}"


currency_table = CurrencyTable()
