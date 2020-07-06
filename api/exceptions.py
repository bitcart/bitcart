class BitcartError(Exception):
    """Generic error class for all errors raised"""


class TemplateDoesNotExistError(BitcartError):
    """Template does not exist and has no default"""


class TemplateLoadError(BitcartError):
    """Failed to load template file from disk"""
