import pytest

from api.ext.ssh import parse_connection_string


@pytest.mark.parametrize(
    ("connection_str", "host", "port", "username"),
    [
        ("", "", 22, ""),
        ("test.com", "test.com", 22, "root"),
        ("user@test.com", "test.com", 22, "user"),
        ("test.com:1", "test.com", 1, "root"),
        ("test.com:invalid", "test.com", 22, "root"),
        ("user@test.com:1", "test.com", 1, "user"),
        ("user@test.com:invalid", "test.com", 22, "user"),
    ],
)
def test_parse_connection_string(connection_str: str, host: str, port: int, username: str) -> None:
    value = parse_connection_string(connection_str)
    assert isinstance(value, tuple)
    assert len(value) == 3
    assert value[0] == host
    assert value[1] == port
    assert value[2] == username
