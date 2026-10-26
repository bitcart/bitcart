import json
import urllib.parse

import pytest

from api.ext import walletpay

CHECKOUT = "https://pay.example.com/i/abc?x=1"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("ethereum:0xabc@56?value=1", 56),
        ("ethereum:0xtoken@1/transfer?address=0xabc&uint256=1", 1),
        ("ethereum:0xabc", None),
        ("ethereum:0xabc@?value=1", None),
        ("bitcoin:tb1q?amount=1", None),
    ],
)
def test_parse_eip681_chain_id(url: str, expected: int | None) -> None:
    assert walletpay.parse_eip681_chain_id(url) == expected


@pytest.mark.parametrize(
    ("coin_name", "network", "payment_url", "expected"),
    [
        ("ETH", "mainnet", "ethereum:0xabc@1?value=1", "eip155:1"),
        ("BNB", "testnet", "ethereum:0xabc@97", "eip155:97"),
        ("ETH", "mainnet", "ethereum:0xabc", None),
        ("TRX", "mainnet", "tron:TAbc", "tron:728126428"),
        ("TRX", "shasta", "tron:TAbc", "tron:2494104990"),
        ("TRX", "nile", "tron:TAbc", "tron:3448148188"),
        ("TRX", "custom", "tron:TAbc", None),
        ("BTC", "mainnet", "bitcoin:bc1q?amount=1", None),
    ],
)
def test_get_network(coin_name: str, network: str, payment_url: str, expected: str | None) -> None:
    assert walletpay.get_network(coin_name, network, payment_url) == expected


def test_get_links_evm_mainnet() -> None:
    assert walletpay.get_links("eip155:1", CHECKOUT) == [
        {"id": "metamask", "name": "MetaMask", "url": "https://link.metamask.io/dapp/pay.example.com/i/abc?x=1"},
        {
            "id": "trust",
            "name": "Trust Wallet",
            "url": "https://link.trustwallet.com/open_url?coin_id=60&url=https%3A%2F%2Fpay.example.com%2Fi%2Fabc%3Fx%3D1",
        },
    ]


def test_get_links_tron_mainnet() -> None:
    links = walletpay.get_links("tron:728126428", CHECKOUT)
    assert [link["id"] for link in links] == ["trust", "tronlink"]
    assert "coin_id=195&" in links[0]["url"]
    prefix = "tronlinkoutside://pull.activity?param="
    assert links[1]["url"].startswith(prefix)
    assert json.loads(urllib.parse.unquote(links[1]["url"].removeprefix(prefix))) == {
        "url": CHECKOUT,
        "action": "open",
        "protocol": "TronLink",
        "version": "1.0",
    }


@pytest.mark.parametrize(
    ("network", "expected"),
    [
        ("eip155:56", ["metamask", "trust"]),
        ("eip155:137", ["metamask", "trust"]),
        ("eip155:11155111", ["metamask"]),
        ("tron:3448148188", ["tronlink"]),
        (None, []),
    ],
)
def test_get_links_wallets(network: str | None, expected: list[str]) -> None:
    assert [link["id"] for link in walletpay.get_links(network, CHECKOUT)] == expected


def test_metamask_link_strips_http_scheme() -> None:
    assert walletpay.get_links("eip155:1", "http://localhost:3000/i/abc")[0]["url"] == (
        "https://link.metamask.io/dapp/localhost:3000/i/abc"
    )
