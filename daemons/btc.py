import argparse
import asyncio
import functools
import inspect
import os
import sys
import traceback
from decimal import Decimal
from types import ModuleType
from typing import Union
from urllib.parse import urlparse

from base import BaseDaemon
from utils import (
    JsonResponse,
    async_partial,
    cached,
    format_satoshis,
    get_exception_message,
    get_function_header,
    hide_logging_errors,
    modify_payment_url,
    rpc,
)


class BTCDaemon(BaseDaemon):
    name = "BTC"
    BASE_SPEC_FILE = "daemons/spec/btc.json"
    DEFAULT_PORT = 5000

    # specify the module in subclass to use features from
    electrum: ModuleType
    # lightning support
    LIGHTNING_SUPPORTED = True
    # whether client is using asyncio or is synchronous
    ASYNC_CLIENT = True
    # map electrum events to bitcart's own events
    # we will only subscribe to the event keys specified
    EVENT_MAPPING = {
        "blockchain_updated": "new_block",
        "new_transaction": "new_transaction",
        "request_status": "new_payment",
        "verified": "verified_tx",
    }
    ALIASES = {"getrequest": "get_request"}
    # override if your daemon has different networks than default electrum provides
    NETWORK_MAPPING: dict = {}

    def register_aliases(self):
        for alias, func in self.ALIASES.items():
            if func in self.supported_methods:
                self.supported_methods[alias] = self.supported_methods[func]

    def load_electrum(self):
        import electrum

        self.electrum = electrum

    def __init__(self):
        self.load_electrum()
        super().__init__()
        self.latest_height = -1  # to avoid duplicate block notifications
        # activate network and configure logging
        activate_selected_network = self.NETWORK_MAPPING.get(self.NET.lower())
        if not activate_selected_network:
            raise ValueError(
                f"Invalid network passed: {self.NET}. Valid choices are {', '.join(self.NETWORK_MAPPING.keys())}."
            )
        activate_selected_network()
        self.setup_config_and_logging()
        # initialize wallet storages
        self.wallets = {}
        self.wallets_updates = {}
        # initialize not yet created network
        self.loop = None
        self.network = None
        self.fx = None
        self.daemon = None

    def load_env(self):
        super().load_env()
        self.LIGHTNING = self.env("LIGHTNING", cast=bool, default=False) if self.LIGHTNING_SUPPORTED else False
        self.LIGHTNING_LISTEN = self.env("LIGHTNING_LISTEN", cast=str, default="") if self.LIGHTNING_SUPPORTED else ""
        self.LIGHTNING_GOSSIP = self.env("LIGHTNING_GOSSIP", cast=bool, default=False) if self.LIGHTNING_SUPPORTED else False
        self.EXCHANGE = self.env(
            "FIAT_EXCHANGE",
            default=self.electrum.exchange_rate.DEFAULT_EXCHANGE,
        )
        self.SERVER = self.env("SERVER", default="")
        self.ONESERVER = self.env("ONESERVER", cast=bool, default=False)
        self.PROXY_URL = self.env("PROXY_URL", default=None)
        self.NETWORK_MAPPING = self.NETWORK_MAPPING or {
            "mainnet": self.electrum.constants.set_mainnet,
            "testnet": self.electrum.constants.set_testnet,
            "regtest": self.electrum.constants.set_regtest,
            "simnet": self.electrum.constants.set_simnet,
            "signet": self.electrum.constants.set_signet,
        }

    def get_proxy_settings(self):
        proxy = None
        if self.PROXY_URL:
            try:
                parsed = urlparse(self.PROXY_URL)
                proxy = {
                    "mode": str(parsed.scheme),
                    "host": str(parsed.hostname),
                    "port": str(parsed.port),
                    "user": str(parsed.username),
                    "password": str(parsed.password),
                }
                proxy = self.electrum.network.serialize_proxy(proxy)
            except Exception:
                sys.exit(f"Invalid proxy URL. Original traceback:\n{traceback.format_exc()}")
        return {"proxy": proxy}

    @property
    @cached
    def available_events(self):
        return list(self.EVENT_MAPPING.keys())

    @property
    @cached
    def config_options(self):
        options = {
            "verbosity": self.VERBOSE,
            "lightning": self.LIGHTNING,  # used by SDK to query whether lightning is enabled
            "lightning_listen": self.LIGHTNING_LISTEN,
            "use_gossip": self.LIGHTNING_GOSSIP,
            "use_exchange": self.EXCHANGE,
            "server": self.SERVER,
            "oneserver": self.ONESERVER,
            "use_exchange_rate": True,
            "forget_config": True,
            "electrum_path": self.DATA_PATH,
            self.NET.lower(): True,
        }
        options.update(self.get_proxy_settings())
        return options

    def create_config(self):
        return self.electrum.simple_config.SimpleConfig(options=self.config_options)

    def setup_config_and_logging(self):
        self.electrum_config = self.create_config()
        self.copy_config_settings(self.electrum_config)
        self.configure_logging(self.electrum_config)

    def configure_logging(self, electrum_config):
        self.electrum.logging.configure_logging(electrum_config)

    def create_daemon(self):
        self.electrum.util._asyncio_event_loop = self.loop
        return self.electrum.daemon.Daemon(self.electrum_config, listen_jsonrpc=False)

    def register_callbacks(self, callback_function):
        for event in self.available_events:
            self.electrum.util.register_callback(async_partial(callback_function, event), [event])

    async def on_startup(self, app):
        await super().on_startup(app)
        self.loop = asyncio.get_running_loop()
        self.daemon = self.create_daemon()
        self.network = self.daemon.network
        callback_function = self._process_events if self.ASYNC_CLIENT else self._process_events_sync
        self.register_callbacks(callback_function)
        self.fx = self.daemon.fx

    async def shutdown_daemon(self):
        if self.daemon:
            await self.daemon.stop()

    async def on_shutdown(self, app):
        await self.shutdown_daemon()
        await super().on_shutdown(app)

    def create_commands(self, config):
        return self.electrum.commands.Commands(config=config, network=self.network, daemon=self.daemon)

    async def restore_wallet(self, command_runner, xpub, config, wallet_path=None):
        return self.electrum.wallet.restore_wallet_from_text(xpub, path=wallet_path, config=config)

    def load_cmd_wallet(self, cmd, wallet):
        if wallet.storage is not None:
            self.daemon.add_wallet(wallet)

    def create_wallet(self, storage, config):
        db = self.electrum.wallet_db.WalletDB(storage.read(), manual_upgrades=False)
        return self.electrum.wallet.Wallet(db=db, storage=storage, config=config)

    def init_wallet(self, wallet):
        if self.LIGHTNING:
            try:
                wallet.init_lightning(password=None)
            except AssertionError:
                pass
        wallet.start_network(self.network)

    def copy_config_settings(self, config):
        config.set_key("currency", self.DEFAULT_CURRENCY)

    # when daemon is syncing or is synced and wallet is not, prevent running commands to avoid unexpected results
    def is_still_syncing(self, wallet=None):
        server_height = self.network.get_server_height()
        server_lag = self.network.get_local_height() - server_height
        # if wallet has unverified_tx, it means that SPV hasn't finished yet
        return (
            self.network.is_connecting()
            or self.network.is_connected()
            and (server_height == 0 or server_lag > 1 or (wallet and not wallet.is_up_to_date()))
        )

    async def load_wallet(self, xpub, config, diskless=False):
        if xpub in self.wallets:
            wallet_data = self.wallets[xpub]
            return wallet_data["wallet"], wallet_data["cmd"]
        command_runner = self.create_commands(config)
        if not xpub:
            return None, command_runner

        if diskless:
            wallet = (await self.restore_wallet(command_runner, xpub, config))["wallet"]
        else:
            wallet_dir = os.path.dirname(config.get_wallet_path())
            wallet_path = os.path.join(wallet_dir, xpub)
            if not os.path.exists(wallet_path):
                await self.restore_wallet(command_runner, xpub, config, wallet_path=wallet_path)
            storage = self.electrum.storage.WalletStorage(wallet_path)
            wallet = self.create_wallet(storage, config)
        self.init_wallet(wallet)
        self.load_cmd_wallet(command_runner, wallet)
        self.wallets[xpub] = {"wallet": wallet, "cmd": command_runner}
        self.wallets_updates[xpub] = []
        return wallet, command_runner

    def add_wallet_to_command(self, wallet, req_method, exec_method, **kwargs):
        method_data = self.get_method_data(req_method, custom=False)
        if method_data.requires_wallet:
            exec_method = functools.partial(exec_method, wallet=wallet)
        return exec_method

    def get_method_data(self, method, custom):
        if custom:
            return self.supported_methods[method]
        else:
            method = self.ALIASES.get(method, method)
            return self.electrum.commands.known_commands[method]

    async def _get_wallet(self, id, req_method, xpub, diskless=False):
        wallet = cmd = error = None
        try:
            wallet, cmd = await self.load_wallet(xpub, config=self.electrum_config, diskless=diskless)
            while self.is_still_syncing(wallet):
                await asyncio.sleep(0.1)
        except Exception as e:
            if self.VERBOSE:
                print(traceback.format_exc())
            if req_method not in self.supported_methods or self.supported_methods[req_method].requires_wallet:
                error_message = self.get_exception_message(e)
                error = JsonResponse(
                    code=self.get_error_code(error_message, fallback_code=-32005),
                    error=error_message,
                    id=id,
                )
        return wallet, cmd, error

    async def get_exec_method(self, cmd, id, req_method):
        error = None
        exec_method = None
        if req_method in self.supported_methods:
            exec_method, custom = self.supported_methods[req_method], True
        else:
            custom = False
            req_method = self.ALIASES.get(req_method, req_method)
            if hasattr(cmd, req_method):
                exec_method = getattr(cmd, req_method)
            else:
                error = JsonResponse(code=-32601, error="Procedure not found", id=id)
        return exec_method, custom, error

    async def get_exec_result(self, xpub, req_method, req_args, req_kwargs, exec_method, custom, **kwargs):
        wallet = kwargs.pop("wallet", None)
        if not custom:
            exec_method = self.add_wallet_to_command(wallet, req_method, exec_method, **kwargs)
        else:
            exec_method = functools.partial(exec_method, wallet=xpub)
        if self.LIGHTNING and self.get_method_data(req_method, custom).requires_lightning and not wallet.has_lightning():
            raise Exception("Lightning not supported in this wallet type")
        with hide_logging_errors(not self.VERBOSE):
            result = exec_method(*req_args, **req_kwargs)
            return await result if inspect.isawaitable(result) else result

    def get_exception_message(self, e):
        if isinstance(e, self.electrum.network.UntrustedServerReturnedError):
            return get_exception_message(e.original_exception)
        return get_exception_message(e)

    async def execute_method(self, id, req_method, xpub, contract, extra_params, req_args, req_kwargs):
        wallet, cmd, error = await self._get_wallet(id, req_method, xpub, diskless=extra_params.get("diskless", False))
        if error:
            return error.send()
        exec_method, custom, error = await self.get_exec_method(cmd, id, req_method)
        if error:
            return error.send()
        if self.get_method_data(req_method, custom).requires_wallet and not xpub:
            return JsonResponse(code=-32000, error="Wallet not loaded", id=id).send()
        try:
            result = await self.get_exec_result(
                xpub, req_method, req_args, req_kwargs, exec_method, custom, wallet=wallet, config=self.electrum_config
            )
            return JsonResponse(result=result, id=id).send()
        except BaseException as e:
            if self.VERBOSE:
                print(traceback.format_exc())
            error_message = self.get_exception_message(e)
            return JsonResponse(code=self.get_error_code(error_message), error=error_message, id=id).send()

    async def _process_events(self, event, *args):
        mapped_event = self.EVENT_MAPPING.get(event)
        data = {"event": mapped_event}
        data_got = None
        try:
            result = self.process_events(mapped_event, *args)
            if inspect.isawaitable(result):
                result = await result
            data_got, wallet = result
        except Exception:
            return
        if data_got is None:
            return
        data.update(data_got)
        if not wallet:
            await self.notify_websockets(data, None, notify_all=True)
        for i in self.wallets:
            if not wallet or wallet == self.wallets[i]["wallet"]:
                if wallet == self.wallets[i]["wallet"]:
                    await self.notify_websockets(data, i, notify_all=True)
                await self.notify_websockets(data, i)
                self.wallets_updates[i].append(data)

    def _process_events_sync(self, event, *args):
        # NOTE: for sync clients it might not guarantee the right execution order because of event loop nature
        # calling .result() here would result in a deadlock, because the code is run in main thread and not network thread
        # revert this change if it would cause issues in the future
        asyncio.run_coroutine_threadsafe(self._process_events(event, *args), self.loop)

    def process_new_block(self):
        height = self.network.get_local_height()
        if height > self.latest_height:
            self.latest_height = height
            return height

    def process_new_transaction(self, args):
        wallet, tx = args
        data = {"tx": tx.txid()}
        return data, wallet

    def process_verified_tx(self, args):
        wallet, tx_hash, tx_mined_status = args
        data = {
            "tx": tx_hash,
            "height": tx_mined_status.height,
        }
        return data, wallet

    def get_status_str(self, status):
        return self.electrum.invoices.pr_tooltips[status]

    def _get_request(self, wallet, address):
        return wallet.get_request(address)

    def _get_request_address(self, invoice):
        return invoice.get_address()

    def get_tx_hashes_for_invoice(self, wallet, invoice):
        return wallet._is_onchain_invoice_paid(invoice)[2]

    def is_paid_via_lightning(self, wallet, invoice):
        return (
            self.LIGHTNING_SUPPORTED
            and invoice.is_lightning()
            and wallet.lnworker
            and wallet.lnworker.get_invoice_status(invoice) == self.electrum.invoices.PR_PAID
        )

    def process_events(self, event, *args):
        """Override in your subclass if needed"""
        wallet = None
        data = {}
        if event == "new_block":
            height = self.process_new_block()
            if not isinstance(height, int):
                return None, None
            data["height"] = height
        elif event == "new_transaction":
            data, wallet = self.process_new_transaction(args)
        elif event == "new_payment":
            wallet, address, status = args
            request = self._get_request(wallet, address)
            paid_via_lightning = self.is_paid_via_lightning(wallet, request)
            tx_hashes = self.get_tx_hashes_for_invoice(wallet, request) if not paid_via_lightning else [request.rhash]
            sent_amount = (
                self.get_sent_amount(wallet, self._get_request_address(request), tx_hashes)
                if not paid_via_lightning
                else format_satoshis(request.get_amount_sat())
            )
            data = {
                "address": str(address),
                "status": status,
                "status_str": self.get_status_str(status),
                "tx_hashes": tx_hashes,
                "sent_amount": sent_amount,
            }
        elif event == "verified_tx":
            data, wallet = self.process_verified_tx(args)
        else:
            return None, None
        return data, wallet

    def get_sent_amount(self, wallet, address, tx_hashes):
        sent_amount = 0
        for tx in tx_hashes:
            sent_amount += wallet.db.get_transaction(tx).output_value_for_address(address)
        return format_satoshis(sent_amount)

    @rpc(requires_wallet=True)
    async def get_request(self, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        wallet_obj = self.wallets[wallet]["wallet"]
        request = self._get_request(wallet_obj, *args, **kwargs)
        result = wallet_obj.export_request(request)
        paid_via_lightning = self.is_paid_via_lightning(wallet_obj, request)
        if paid_via_lightning:
            result["tx_hashes"] = [request.rhash]
        result["sent_amount"] = (
            self.get_sent_amount(wallet_obj, result["address"], result["tx_hashes"])
            if not paid_via_lightning
            else format_satoshis(request.get_amount_sat())
        )
        return result

    @rpc
    def validatekey(self, key, wallet=None):
        return self.electrum.keystore.is_master_key(key) or self.electrum.keystore.is_seed(key)

    @rpc(requires_wallet=True)
    def get_updates(self, wallet):
        updates = self.wallets_updates[wallet]
        self.wallets_updates[wallet] = []
        return updates

    async def _verify_transaction(self, tx_hash, tx_height):
        merkle = await self.network.get_merkle_for_transaction(tx_hash, tx_height)
        tx_height = merkle.get("block_height")
        pos = merkle.get("pos")
        merkle_branch = merkle.get("merkle")
        header = self.network.blockchain().read_header(tx_height)
        if header is None and tx_height <= self.network.get_local_height():
            await self.network.request_chunk(tx_height, None, can_return_early=True)
            header = self.network.blockchain().read_header(tx_height)
        self.electrum.verifier.verify_tx_is_in_block(tx_hash, merkle_branch, pos, header, tx_height)

    async def _get_transaction_verbose(self, tx_hash):
        result = await self.network.interface.session.send_request("blockchain.transaction.get", [tx_hash, True])
        tx = self.electrum.transaction.Transaction(result["hex"])
        tx.deserialize()
        result_formatted = tx.to_json()
        result_formatted.update({"confirmations": result.get("confirmations", 0)})
        return result_formatted

    async def _get_transaction_spv(self, tx_hash):
        # Temporarily used to remove frequent CI failures in get_tx until electrum protocol 1.5 is released
        # Note that this is not efficient, that's why it's not default yet
        result = await self.network.get_transaction(tx_hash)
        tx = self.electrum.transaction.Transaction(result)
        tx.deserialize()
        result_formatted = tx.to_json()
        address = None
        for output in result_formatted["outputs"]:
            if output["address"] is not None:
                address = output["address"]
                break
        if address is None:
            raise Exception("Invalid transaction: output address is None")
        scripthash = self.electrum.bitcoin.address_to_scripthash(address)
        history = await self.network.get_history_for_scripthash(scripthash)
        tx_height = None
        for tx_info in history:
            if tx_info["tx_hash"] == tx_hash:
                tx_height = tx_info["height"]
                break
        if tx_height is None:
            raise Exception("Invalid transaction: not included in address histories")
        current_height = self.network.get_local_height()
        confirmations = 0 if tx_height == 0 else current_height - tx_height + 1
        result_formatted.update({"confirmations": confirmations})
        await self._verify_transaction(tx_hash, tx_height)
        return result_formatted

    @rpc
    async def get_transaction(self, tx_hash, use_spv=False, wallet=None):
        return await self._get_transaction_spv(tx_hash) if use_spv else await self._get_transaction_verbose(tx_hash)

    @rpc
    def exchange_rate(self, currency=None, wallet=None) -> str:
        if currency is None:
            currency = self.DEFAULT_CURRENCY
        if self.fx.get_currency() != currency:
            self.fx.set_currency(currency)
        return str(self.fx.exchange_rate())

    @rpc
    def list_currencies(self, wallet=None) -> list:
        return self.fx.get_currencies(False)

    @rpc
    def get_tx_size(self, raw_tx: dict, wallet=None) -> int:
        return self.electrum.transaction.Transaction(raw_tx).estimated_size()

    @rpc
    def get_tx_hash(self, raw_tx: dict, wallet=None) -> int:
        return self.electrum.transaction.Transaction(raw_tx).txid()

    @rpc
    def get_default_fee(self, tx: Union[str, int], wallet=None) -> float:
        return format_satoshis(self.electrum_config.estimate_fee(self.get_tx_size(tx) if isinstance(tx, str) else tx))

    @rpc
    def recommended_fee(self, target, wallet=None) -> float:
        return self.electrum_config.eta_target_to_fee(target)

    @rpc(requires_wallet=True)
    def get_invoice(self, key, wallet):
        value = self.wallets[wallet]["wallet"].get_formatted_request(key)
        if not value:
            raise Exception("Invoice not found")
        return value

    def get_address_balance(self, address, wallet):
        return self.wallets[wallet]["wallet"].get_addr_balance(address)

    @rpc(requires_wallet=True)
    def getaddressbalance_wallet(self, address, wallet):
        confirmed, unconfirmed, unmatured = map(format_satoshis, self.get_address_balance(address, wallet))
        return {"confirmed": confirmed, "unconfirmed": unconfirmed, "unmatured": unmatured}

    @rpc
    def validatecontract(self, address, wallet=None):  # fallback for other coins without smart contracts
        return False

    @rpc
    def get_tokens(self, wallet=None):  # fallback
        return {}

    @rpc
    def getabi(self, wallet=None):  # fallback
        return []

    @rpc
    def normalizeaddress(self, address, wallet=None):  # fallback
        return address

    @rpc(requires_wallet=True)  # fallback
    def setrequestaddress(self, key, address, wallet):
        return False

    @rpc
    async def getinfo(self, wallet=None):
        data = await self.create_commands(config=self.electrum_config).getinfo()
        data["synchronized"] = not self.is_still_syncing()
        return data

    @rpc(requires_wallet=True, requires_network=True)
    async def get_used_fee(self, tx_hash, wallet):
        tx = self.wallets[wallet]["wallet"].db.get_transaction(tx_hash)
        if tx is None:
            raise Exception("No such blockchain transaction")
        delta = self.wallets[wallet]["wallet"].get_wallet_delta(tx)
        return format_satoshis(delta.fee)

    @rpc
    async def modifypaymenturl(self, url, amount, divisibility=None, wallet=None):
        try:
            lnaddr = self.electrum.lnaddr.lndecode(url)
            if wallet not in self.wallets:
                raise Exception("Wallet not loaded")
            lnaddr.amount = Decimal(amount)
            return self.electrum.lnaddr.lnencode(lnaddr, self.wallets[wallet]["wallet"].lnworker.node_keypair.privkey)
        except Exception as e:
            if str(e) == "Wallet not loaded":
                raise
            return modify_payment_url("amount", url, amount)

    @rpc(requires_wallet=True)
    async def adjustforhwsign(self, tx, fingerprint, derivation, wallet):
        self.wallets[wallet]["wallet"].keystore.add_key_origin(derivation_prefix=derivation, root_fingerprint=fingerprint)
        tx = self.electrum.transaction.tx_from_any(tx)
        tx.add_info_from_wallet(self.wallets[wallet]["wallet"])
        tx.prepare_for_export_for_hardware_device(self.wallets[wallet]["wallet"])
        return str(tx)

    @rpc
    async def getfingerprint(self, xpub, wallet=None):
        return self.electrum.bip32.root_fp_and_der_prefix_from_xkey(xpub)[0]

    @rpc(requires_wallet=True, requires_network=True)
    async def finalizepsbt(self, psbt, wallet):
        tx = self.electrum.transaction.tx_from_any(psbt)
        tx.add_info_from_wallet(self.wallets[wallet]["wallet"])
        return tx.serialize_to_network()

    async def get_commands_list(self, commands):
        return await commands.help()

    @rpc
    async def help(self, func=None, wallet=None):
        commands = self.create_commands(config=self.electrum_config)
        if func is None:
            data = await self.get_commands_list(commands)
            data.extend(list(self.supported_methods.keys()))
            data.extend(list(self.ALIASES.keys()))
            return data
        if func in self.supported_methods:
            return get_function_header(func, self.supported_methods[func])
        elif hasattr(commands, func):
            # WARNING: dark magic of introspection
            parser = self.electrum.commands.get_parser()
            all_actions = parser._actions
            sub_action = None
            for action in all_actions:
                if isinstance(action, argparse._SubParsersAction):
                    sub_action = action
                    break
            command_parser = sub_action.choices[func]
            group_global = command_parser._action_groups.pop()
            require_path = func in ["restore", "create"]
            command_parser._actions = list(
                filter(
                    lambda x: x not in group_global._group_actions
                    and x.dest not in ["forget_config", "help"]
                    and (x.dest != "wallet_path" or require_path),
                    command_parser._actions,
                )
            )
            command_parser._action_groups[1]._group_actions = list(
                filter(
                    lambda x: x.dest not in ["forget_config", "help"] and (x.dest != "wallet_path" or require_path),
                    command_parser._action_groups[1]._group_actions,
                )
            )
            command_parser.prog = f"bitcart-cli {func}"
            return command_parser.format_help()
        else:
            raise Exception("Procedure not found")

    @rpc(requires_wallet=True, requires_network=True)
    async def close_wallet(self, wallet):
        method = self.wallets[wallet]["cmd"].close_wallet
        await method() if self.ASYNC_CLIENT else method()
        del self.wallets_updates[wallet]
        del self.wallets[wallet]
        return True


if __name__ == "__main__":
    daemon = BTCDaemon()
    daemon.start()
