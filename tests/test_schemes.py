from api import schemes


def test_http_create_token_validator():
    assert schemes.HTTPCreateLoginToken(permissions="").permissions == []
