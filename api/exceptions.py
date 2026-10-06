class BitcartError(Exception):
    """Generic error class for all errors raised"""


class TemplateDoesNotExistError(BitcartError):
    """Template does not exist and has no default"""


class TemplateLoadError(BitcartError):
    """Failed to load template file from disk"""


class ExchangeRateError(BitcartError):
    """No exchange rate could be used"""


class ExchangeRatesUnavailableError(ExchangeRateError):
    """The worker did not answer an exchange rates request"""


class RateUnavailableError(ExchangeRateError):
    """No valid exchange rate for a currency pair"""

    def __init__(self, left: str, right: str) -> None:
        super().__init__(f"No exchange rate available for {left}_{right}")
        self.left = left
        self.right = right
