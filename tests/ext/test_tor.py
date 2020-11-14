import ipaddress

from api.ext.tor import (
    HiddenService,
    PortDefinition,
    get_hostname,
    get_service_name,
    is_onion,
    parse_hidden_service,
    parse_hidden_service_port,
    parse_torrc,
)


def test_is_onion():
    assert not is_onion("test.com")
    assert is_onion("test.onion")
    assert is_onion("TEST.ONION")
    assert not is_onion("TEST.COM")


def test_parse_hidden_service():
    assert not parse_hidden_service("test")
    assert not parse_hidden_service("HiddenServiceDir")
    assert not parse_hidden_service("HiddenServiceDir ")
    assert not parse_hidden_service("HiddenServiceDir test 1")
    assert parse_hidden_service("HiddenServiceDir test") == "test"


def test_parse_hidden_service_port():
    assert not parse_hidden_service_port("test")
    assert not parse_hidden_service_port("HiddenServicePort")
    assert not parse_hidden_service_port("HiddenServicePort test")
    assert not parse_hidden_service_port("HiddenServicePort ")
    assert not parse_hidden_service_port("HiddenServicePort test 1 2")
    assert not parse_hidden_service_port("HiddenServicePort test test2")
    assert not parse_hidden_service_port("HiddenServicePort 80 test")
    assert not parse_hidden_service_port("HiddenServicePort 80 127.0.0.1")
    assert not parse_hidden_service_port("HiddenServicePort 80 127.0.0.1:t")
    assert parse_hidden_service_port("HiddenServicePort 80 127.0.0.1:80") == PortDefinition(
        80, str(ipaddress.ip_address("127.0.0.1")), 80
    )


def test_get_hostname(service_dir):
    assert not get_hostname("test")
    hostname = get_hostname(service_dir)
    assert hostname == "http://test.onion"
    assert is_onion(hostname)


def test_get_service_name():
    assert get_service_name("test-1") == "test 1"
    assert get_service_name("BitcartCC-Merchants-API") == "BitcartCC Merchants API"


def test_parse_torrc(torrc):
    assert not parse_torrc(None)
    assert not parse_torrc("test")
    assert parse_torrc(torrc) == [
        HiddenService(
            "test 1",
            "test-1",
            "http://test.onion",
            PortDefinition(80, str(ipaddress.ip_address("127.0.0.1")), 80),
        )
    ]
