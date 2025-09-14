import ipaddress
import os
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI

from api.services.ext.tor import HiddenService, PortDefinition, TorService


@pytest.fixture
async def tor_service(app: FastAPI) -> AsyncIterator[TorService]:
    yield await app.state.dishka_container.get(TorService)


def test_is_onion(tor_service: TorService) -> None:
    assert not tor_service.is_onion("test.com")
    assert tor_service.is_onion("test.onion")
    assert tor_service.is_onion("TEST.ONION")
    assert not tor_service.is_onion("TEST.COM")


def test_parse_hidden_service(tor_service: TorService) -> None:
    assert not tor_service.parse_hidden_service("test")
    assert not tor_service.parse_hidden_service("HiddenServiceDir")
    assert not tor_service.parse_hidden_service("HiddenServiceDir ")
    assert not tor_service.parse_hidden_service("HiddenServiceDir test 1")
    assert tor_service.parse_hidden_service("HiddenServiceDir test") == "test"


def test_parse_hidden_service_port(tor_service: TorService) -> None:
    assert not tor_service.parse_hidden_service_port("test")
    assert not tor_service.parse_hidden_service_port("HiddenServicePort")
    assert not tor_service.parse_hidden_service_port("HiddenServicePort test")
    assert not tor_service.parse_hidden_service_port("HiddenServicePort ")
    assert not tor_service.parse_hidden_service_port("HiddenServicePort test 1 2")
    assert not tor_service.parse_hidden_service_port("HiddenServicePort test test2")
    assert not tor_service.parse_hidden_service_port("HiddenServicePort 80 test")
    assert not tor_service.parse_hidden_service_port("HiddenServicePort 80 127.0.0.1")
    assert not tor_service.parse_hidden_service_port("HiddenServicePort 80 127.0.0.1:t")
    assert tor_service.parse_hidden_service_port("HiddenServicePort 80 127.0.0.1:80") == PortDefinition(
        80, str(ipaddress.ip_address("127.0.0.1")), 80
    )


def test_get_hostname(service_dir: str, tor_service: TorService) -> None:
    assert not tor_service.get_hostname("test")
    hostname = tor_service.get_hostname(service_dir)
    assert hostname == "http://test.onion"
    assert tor_service.is_onion(hostname)


def test_get_service_name(tor_service: TorService) -> None:
    assert tor_service.get_service_name("test-1") == "test 1"
    assert tor_service.get_service_name("Bitcart-Merchants-API") == "Bitcart Merchants API"


def test_parse_torrc(torrc: str, service_dir: str, tor_service: TorService) -> None:
    assert not tor_service.parse_torrc(None)
    assert not tor_service.parse_torrc("test")
    assert tor_service.parse_torrc(torrc) == [
        HiddenService(
            os.path.basename(service_dir),
            service_dir,
            "http://test.onion",
            PortDefinition(80, str(ipaddress.ip_address("127.0.0.1")), 80),
        )
    ]
