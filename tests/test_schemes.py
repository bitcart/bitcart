from api import schemes


def test_http_create_token_validator():
    assert schemes.HTTPCreateLoginToken(permissions="").permissions == []


def test_invoice_tx_hashes_validator():
    assert schemes.Invoice(tx_hashes="", price=5, user_id="1", sent_amount="0").tx_hashes == []
