from typing import Any, cast

from bitcart import (  # type: ignore[attr-defined]
    BTC,
    COINS,
    APIManager,
)
from fastapi import HTTPException

from api.ext.blockexplorer import EXPLORERS
from api.ext.rpc import RPC
from api.services.plugin_registry import PluginRegistry
from api.settings import Settings


class CoinService:
    def __init__(self, settings: Settings, plugin_registry: PluginRegistry) -> None:
        self.settings = settings
        self.plugin_registry = plugin_registry
        self.load_cryptos()

    def load_cryptos(self) -> None:
        self._cryptos: dict[str, BTC] = {}
        self._crypto_settings = {}
        self.manager = APIManager({crypto.upper(): [] for crypto in self.settings.ENABLED_CRYPTOS})
        for crypto in self.settings.ENABLED_CRYPTOS:
            env_name = crypto.upper()
            coin = COINS[env_name]
            default_url = coin.RPC_URL
            default_user = coin.RPC_USER
            default_password = coin.RPC_PASS
            _, default_host, default_port_str = default_url.split(":")
            default_host = default_host[2:]
            default_port = int(default_port_str)
            rpc_host = self.settings.config(f"{env_name}_HOST", default=default_host)
            rpc_port = self.settings.config(f"{env_name}_PORT", cast=int, default=default_port)
            rpc_url = f"http://{rpc_host}:{rpc_port}"
            rpc_user = self.settings.config(f"{env_name}_LOGIN", default=default_user)
            rpc_password = self.settings.config(f"{env_name}_PASSWORD", default=default_password)
            crypto_network = self.settings.config(f"{env_name}_NETWORK", default="mainnet")
            crypto_lightning = self.settings.config(f"{env_name}_LIGHTNING", cast=bool, default=False)
            credentials: dict[str, Any] = {"rpc_url": rpc_url, "rpc_user": rpc_user, "rpc_pass": rpc_password}
            self._crypto_settings[crypto] = {
                "credentials": credentials,
                "network": crypto_network,
                "lightning": crypto_lightning,
            }
            self._cryptos[crypto] = coin(**credentials)
            self.manager.wallets[env_name][""] = self._cryptos[crypto]

    def get_coin_list(self) -> list[str]:
        return list(self._cryptos.keys())

    def get_coin_settings(self, currency: str) -> dict[str, Any] | None:
        return self._crypto_settings.get(currency.lower())

    @property
    def cryptos(self) -> dict[str, BTC]:
        return self._cryptos

    @property
    def crypto_settings(self) -> dict[str, dict[str, Any]]:
        return self._crypto_settings

    async def get_coin(self, coin: str, xpub: str | dict[str, Any] | None = None) -> BTC:
        coin = coin.lower()
        if coin not in self._cryptos:
            raise HTTPException(422, "Unsupported currency")
        if not xpub:
            return self._cryptos[coin]
        obj = None
        if coin.upper() in COINS:
            obj = COINS[coin.upper()](
                xpub=xpub,  # type: ignore # TODO: fix in bitcart
                **cast(dict[str, Any], self._crypto_settings[coin]["credentials"]),
            )
        return await self.plugin_registry.apply_filters("get_coin", obj, coin, xpub)

    async def get_default_explorer(self, coin: str) -> str:
        coin = coin.lower()
        if coin not in self.cryptos:
            raise HTTPException(422, "Unsupported currency")
        explorer = ""
        if coin in self._crypto_settings:
            explorer = EXPLORERS.get(coin, {}).get(self._crypto_settings[coin]["network"], "")
        return await self.plugin_registry.apply_filters("get_coin_explorer", explorer, coin)

    def get_default_rpc(self, coin: str) -> str:
        coin = coin.lower()
        if coin not in self.cryptos:
            raise HTTPException(422, "Unsupported currency")
        if not self._cryptos[coin].is_eth_based:
            return ""
        return RPC.get(coin, {}).get(self._crypto_settings[coin]["network"], "")
