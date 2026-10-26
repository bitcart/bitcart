import json
import urllib.parse
from collections.abc import Callable

TRON_CHAIN_IDS = {"mainnet": 728126428, "shasta": 2494104990, "nile": 3448148188}

TRUST_WALLET_COIN_IDS = {"eip155:1": 60, "eip155:56": 20000714, "eip155:137": 966, "tron:728126428": 195}


def parse_eip681_chain_id(url: str) -> int | None:
    if not url.startswith("ethereum:"):
        return None
    _, sep, rest = url.partition("@")
    digits = ""
    for char in rest:
        if not char.isdigit():
            break
        digits += char
    return int(digits) if sep and digits else None


def get_network(coin_name: str, network: str, payment_url: str) -> str | None:
    if coin_name == "TRX":
        tron_chain_id = TRON_CHAIN_IDS.get(network)
        return f"tron:{tron_chain_id}" if tron_chain_id else None
    chain_id = parse_eip681_chain_id(payment_url)
    return f"eip155:{chain_id}" if chain_id else None


def metamask_link(network: str, url: str) -> str | None:
    if not network.startswith("eip155:"):
        return None
    return f"https://link.metamask.io/dapp/{url.removeprefix('https://').removeprefix('http://')}"


def trust_wallet_link(network: str, url: str) -> str | None:
    coin_id = TRUST_WALLET_COIN_IDS.get(network)
    if coin_id is None:
        return None
    return f"https://link.trustwallet.com/open_url?coin_id={coin_id}&url={urllib.parse.quote(url, safe='')}"


def tronlink_link(network: str, url: str) -> str | None:
    if not network.startswith("tron:"):
        return None
    param = json.dumps({"url": url, "action": "open", "protocol": "TronLink", "version": "1.0"})
    return f"tronlinkoutside://pull.activity?param={urllib.parse.quote(param, safe='')}"


WALLET_APPS: list[tuple[str, str, Callable[[str, str], str | None]]] = [
    ("metamask", "MetaMask", metamask_link),
    ("trust", "Trust Wallet", trust_wallet_link),
    ("tronlink", "TronLink", tronlink_link),
]


def get_links(network: str | None, url: str) -> list[dict[str, str]]:
    if network is None:
        return []
    links = []
    for wallet_id, name, build_link in WALLET_APPS:
        if link := build_link(network, url):
            links.append({"id": wallet_id, "name": name, "url": link})
    return links
