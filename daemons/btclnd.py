"""BitcoinLND daemon - Bitcart altcoin daemon using LND in neutrino mode.

This daemon acts as a shim between Bitcart and LND, presenting the same
JSON-RPC interface that Bitcart expects from an Electrum-based wallet.
Each wallet is a separate LND instance identified by its aezeed seed phrase.
"""

from base import BaseDaemon  # isort: skip

import asyncio
import functools
import inspect
import os
import traceback
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import grpc

from electrumx_client import ElectrumXMonitor
from lnd_grpc import LNDGrpcClient
from lnd_process import LNDBinaryManager, LNDProcess, PortManager, TorProcess, is_tor_available, seed_to_wallet_key
from logger import configure_logging, get_logger
from utils import JsonResponse, format_satoshis, get_function_header, modify_payment_url, rpc

logger = get_logger(__name__)

# LND invoice states
INVOICE_OPEN = 0
INVOICE_SETTLED = 1
INVOICE_CANCELED = 2
INVOICE_ACCEPTED = 3

# Bitcart payment request status codes (matching Electrum's PR_* constants)
PR_UNPAID = 0
PR_EXPIRED = 1
PR_UNKNOWN = 2
PR_PAID = 3
PR_INFLIGHT = 4
PR_FAILED = 5
PR_ROUTING = 6
PR_UNCONFIRMED = 7

PR_STATUS_STR = {
    PR_UNPAID: "Pending",
    PR_EXPIRED: "Expired",
    PR_UNKNOWN: "Unknown",
    PR_PAID: "Paid",
    PR_INFLIGHT: "In-flight",
    PR_FAILED: "Failed",
    PR_ROUTING: "Routing",
    PR_UNCONFIRMED: "Unconfirmed",
}

# Aezeed wordlist has 24 words, same as BIP39
AEZEED_WORD_COUNT = 24


@dataclass
class LNDWalletInstance:
    """Represents a single LND wallet instance managed by the daemon."""

    seed: str
    wallet_key: str
    process: LNDProcess
    grpc_client: LNDGrpcClient
    grpc_port: int
    rest_port: int
    p2p_port: int
    data_dir: str
    identity_pubkey: str | None = None
    synced_to_chain: bool = False
    block_height: int = 0
    event_tasks: list = field(default_factory=list)
    tor_process: TorProcess | None = None
    uris: list = field(default_factory=list)
    # Maps payment hash (r_hash hex) → on-chain address for tracking on-chain payments
    request_addresses: dict = field(default_factory=dict)
    # Lock protecting concurrent access to request_addresses
    request_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # ElectrumX monitor for zero-conf on-chain payment detection
    electrumx_monitor: object | None = None


class BTCLNDDaemon(BaseDaemon):
    """Bitcart daemon that uses LND instead of Electrum for Bitcoin operations.

    Manages multiple LND instances (one per wallet), each running in neutrino mode.
    Presents a JSON-RPC interface compatible with what Bitcart expects from
    an Electrum-based daemon.
    """

    name = "BTCLND"
    # Shown to customers in invoices - this is BTC, just using LND backend
    DISPLAY_NAME = "BTC"
    BASE_SPEC_FILE = "daemons/spec/btc.json"
    DEFAULT_PORT = 5012
    LIGHTNING_SUPPORTED = True

    LND_VERSION = "v0.20.1-beta"
    # Fixed wallet password - filesystem security is assumed
    LND_WALLET_PASSWORD = b"bitcart-lnd-password"

    # Map Bitcart network names to LND network names
    NETWORK_MAPPING = {
        "mainnet": "mainnet",
        "testnet": "testnet3",
        "testnet3": "testnet3",
        "testnet4": "testnet4",
        "signet": "signet",
        "regtest": "regtest",
    }

    # Default neutrino peers per network
    DEFAULT_NEUTRINO_PEERS = {
        "mainnet": ["btcd-mainnet.lightning.computer", "faucet.lightning.community"],
        "testnet3": ["faucet.lightning.community"],
        "testnet4": [],
        "signet": [],
        "regtest": [],
    }

    ALIASES = {"getrequest": "get_request"}

    def __init__(self):
        super().__init__()
        # Wallet storage: wallet_key -> LNDWalletInstance
        self.wallets: dict[str, LNDWalletInstance] = {}
        # Event update queues per wallet (for polling)
        self.wallets_updates: dict[str, deque] = {}
        # Resolve data path
        if not self.DATA_PATH:
            self.DATA_PATH = os.path.join(
                os.path.expanduser("~"), ".bitcart-btclnd", self.LND_NETWORK
            )
        os.makedirs(self.DATA_PATH, exist_ok=True)
        self.port_manager = PortManager(
            self.DATA_PATH,
            base_grpc_port=self.BASE_GRPC_PORT,
            base_rest_port=self.BASE_REST_PORT,
            base_p2p_port=self.BASE_P2P_PORT,
        )
        self.binary_manager = LNDBinaryManager(self.DATA_PATH, self.LND_VERSION)
        self.lnd_binary_path: str | None = None
        self.running = True
        # Per-wallet locks to prevent concurrent load_wallet calls
        self._wallet_locks: dict[str, asyncio.Lock] = {}
        # Per-wallet peewee database connections for request tracking
        self._request_dbs: dict = {}

    def register_aliases(self):
        """Register method aliases for backward compatibility."""
        for alias, func_name in self.ALIASES.items():
            if func_name in self.supported_methods:
                self.supported_methods[alias] = self.supported_methods[func_name]

    def load_env(self):
        """Load environment variables specific to the BTCLND daemon."""
        super().load_env()
        # Network configuration
        self.LND_NETWORK = self.NETWORK_MAPPING.get(self.NET.lower())
        if not self.LND_NETWORK:
            valid = ", ".join(self.NETWORK_MAPPING.keys())
            raise ValueError(f"Invalid network: {self.NET}. Valid choices: {valid}")
        # Neutrino peer configuration
        peers_env = self.env("NEUTRINO_PEERS", default="")
        if peers_env:
            self.NEUTRINO_PEERS = [p.strip() for p in peers_env.split(",") if p.strip()]
        else:
            self.NEUTRINO_PEERS = list(
                self.DEFAULT_NEUTRINO_PEERS.get(self.LND_NETWORK, [])
            )
        # Base ports for the per-wallet PortManager. Override these to
        # shift the publicly-exposed p2p range away from defaults that
        # collide with other lightning daemons running on the same host.
        # gRPC and REST stay internal to the daemon; only p2p is published.
        self.BASE_GRPC_PORT = self.env("BASE_GRPC_PORT", cast=int, default=PortManager.BASE_GRPC_PORT)
        self.BASE_REST_PORT = self.env("BASE_REST_PORT", cast=int, default=PortManager.BASE_REST_PORT)
        self.BASE_P2P_PORT = self.env("BASE_P2P_PORT", cast=int, default=PortManager.BASE_P2P_PORT)
        # Host advertised in getlndinfo responses. Defaults to 127.0.0.1 for
        # the common case where callers run on the docker host and the gRPC
        # port range is published to localhost. Set to the daemon service
        # name (e.g. "btclnd") when callers run as sidecars on the same
        # docker network.
        self.GRPC_PUBLIC_HOST = self.env("GRPC_PUBLIC_HOST", default="127.0.0.1")
        # LND binary path (empty = auto-detect/download)
        self.LND_BINARY_PATH = self.env("LND_BINARY", default="")
        # Extra arguments to pass to LND
        self.LND_EXTRA_ARGS = self.env("LND_EXTRA_ARGS", default="")
        # External IP or hostname for clearnet node advertising
        # Required for LND to advertise a clearnet address alongside the Tor address
        # Defaults to the hostname from BITCART_HOST (the host Bitcart is served on)
        external_ip = self.env("EXTERNAL_IP", default="")
        if not external_ip:
            bitcart_host = os.environ.get("BITCART_HOST", "")
            # Strip port if present (e.g., "mysite.com:8000" -> "mysite.com")
            if bitcart_host:
                external_ip = bitcart_host.split(":")[0]
            # Don't use localhost/127.0.0.1 as external IP — it's not routable
            if external_ip in ("localhost", "127.0.0.1", "0.0.0.0", ""):
                external_ip = ""
        self.EXTERNAL_IP = external_ip
        # Tor: auto-enable if Tor binary is available on the system
        tor_env = self.env("TOR", default="auto")
        if tor_env.lower() == "auto":
            self.TOR_ENABLED = is_tor_available()
        else:
            self.TOR_ENABLED = tor_env.lower() in ("true", "1", "yes")
        if self.TOR_ENABLED:
            logger.info("Tor is available, LND wallets will run in hybrid mode (clearnet + Tor)")
        else:
            logger.info("Tor not available, LND wallets will run in clearnet-only mode")

    def set_dynamic_spec(self):
        """Set dynamic capabilities in the spec."""
        self.spec["capabilities"] = {"lightning": True}

    async def on_startup(self, app):
        """Initialize daemon: find/download LND binary, then auto-start known wallets."""
        await super().on_startup(app)
        configure_logging(debug=self.VERBOSE)
        if self.LND_BINARY_PATH:
            self.lnd_binary_path = self.LND_BINARY_PATH
        else:
            self.lnd_binary_path = await self.binary_manager.find_or_download()
        logger.info(
            f"BTCLND daemon starting: network={self.LND_NETWORK}, "
            f"port={self.PORT}, lnd={self.lnd_binary_path}"
        )
        # Auto-start known wallets in the background
        asyncio.create_task(self._auto_start_wallets())

    async def _auto_start_wallets(self):
        """Auto-start all previously known wallets on daemon boot.

        Reads seed_map.json which maps wallet_key -> seed for all wallets
        that have been loaded before. This allows LND instances to start
        immediately without waiting for an API request.
        """
        seed_map = self._load_seed_map()
        if not seed_map:
            return
        logger.info(f"Auto-starting {len(seed_map)} known wallet(s)...")
        for wallet_key, wallet_info in seed_map.items():
            if not self.running:
                break
            try:
                seed = wallet_info["seed"]
                tor = wallet_info.get("tor_enabled")
                zero_conf = wallet_info.get("zero_conf_monitoring")
                await self.load_wallet(seed, tor_enabled=tor, zero_conf=zero_conf)
            except Exception as e:
                logger.error(f"Failed to auto-start wallet {wallet_key}: {e}")

    def _load_seed_map(self) -> dict[str, dict]:
        """Load the seed map from disk.

        Returns dict of wallet_key -> {"seed": str, "tor_enabled": bool}.
        Handles both old format (wallet_key -> seed_str) and new format.
        """
        import json

        path = os.path.join(self.DATA_PATH, "seed_map.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path) as f:
                data = json.load(f)
            # Handle old format: wallet_key -> seed_string
            result = {}
            for wk, val in data.items():
                if isinstance(val, str):
                    result[wk] = {"seed": val, "tor_enabled": self.TOR_ENABLED}
                else:
                    result[wk] = val
            return result
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_seed_map(self):
        """Persist the seed map to disk so wallets can auto-start on next boot.

        Stores both the seed and Tor preference per wallet.
        """
        import json

        path = os.path.join(self.DATA_PATH, "seed_map.json")
        seed_map = {}
        for wk, inst in self.wallets.items():
            seed_map[wk] = {
                "seed": inst.seed,
                "tor_enabled": inst.tor_process is not None,
                "zero_conf_monitoring": inst.electrumx_monitor is not None,
            }
        with open(path, "w") as f:
            json.dump(seed_map, f)

    def _get_request_db(self, wallet_key: str):
        """Get or create the peewee database for on-chain payment request tracking.

        Each wallet has its own SQLite database stored in its data directory.
        Also creates the ElectrumXServer table for server state persistence.
        """
        if wallet_key in self._request_dbs:
            return self._request_dbs[wallet_key]
        from peewee import CompositeKey, Model, SqliteDatabase, TextField, IntegerField

        db_path = os.path.join(self._get_wallet_dir(wallet_key), "requests.db")
        db = SqliteDatabase(db_path)

        class PaymentRequest(Model):
            request_id = TextField(primary_key=True)
            address = TextField()
            amount_sat = IntegerField()

            class Meta:
                database = db
                table_name = "payment_requests"

        class ElectrumXServer(Model):
            host = TextField()
            port = IntegerField()
            protocol = TextField(default="s")
            last_connected = IntegerField(default=0)
            failures = IntegerField(default=0)

            class Meta:
                database = db
                table_name = "electrumx_servers"
                primary_key = CompositeKey("host", "port")

        db.connect()
        db.create_tables([PaymentRequest, ElectrumXServer])
        self._request_dbs[wallet_key] = (db, PaymentRequest, ElectrumXServer)
        return db, PaymentRequest, ElectrumXServer

    def _save_request_address(self, wallet_key: str, request_id: str, address: str, amount_sat: int):
        """Persist a single payment request to the wallet's SQLite database."""
        _, PaymentRequest, _ = self._get_request_db(wallet_key)
        PaymentRequest.replace(
            request_id=request_id, address=address, amount_sat=amount_sat
        ).execute()

    def _load_request_addresses(self, wallet_key: str) -> dict:
        """Load all payment requests from the wallet's SQLite database."""
        db_path = os.path.join(self._get_wallet_dir(wallet_key), "requests.db")
        if not os.path.exists(db_path):
            return {}
        _, PaymentRequest, _ = self._get_request_db(wallet_key)
        return {
            row.request_id: {"address": row.address, "amount_sat": row.amount_sat}
            for row in PaymentRequest.select()
        }

    async def on_shutdown(self, app):
        """Gracefully shut down all LND and Tor instances."""
        self.running = False
        logger.info("Shutting down BTCLND daemon...")
        for wallet_key, wallet_inst in list(self.wallets.items()):
            for task in wallet_inst.event_tasks:
                task.cancel()
            try:
                await wallet_inst.grpc_client.close()
            except Exception:
                pass
            try:
                await wallet_inst.process.stop(timeout=30)
            except Exception:
                pass
            # Stop Tor process if running
            if wallet_inst.tor_process:
                try:
                    await wallet_inst.tor_process.stop()
                except Exception:
                    pass
            # Stop ElectrumX monitor if running
            if wallet_inst.electrumx_monitor:
                try:
                    await wallet_inst.electrumx_monitor.stop()
                except Exception:
                    pass
        self.wallets.clear()
        self.wallets_updates.clear()
        await super().on_shutdown(app)

    # Override to show BTC instead of BTCLND in websocket notifications
    # NOTE: Do NOT override build_notification to change the currency name.
    # The SDK's APIManager uses the currency field to route events internally,
    # so it must match the coin_name ("BTCLND"), not the display name ("BTC").
    # The display name is only used in the customer-facing checkout UI.

    # -------------------------------------------------------------------------
    # Wallet lifecycle management
    # -------------------------------------------------------------------------

    def _get_wallet_key(self, xpub: str | None) -> str | None:
        """Convert seed phrase (xpub) to wallet key."""
        if not xpub:
            return None
        return seed_to_wallet_key(xpub)

    def _get_wallet_dir(self, wallet_key: str) -> str:
        """Get the data directory path for a wallet."""
        return os.path.join(self.DATA_PATH, "wallets", wallet_key)

    async def load_wallet(self, seed: str, tor_enabled: bool | None = None, zero_conf: bool | None = None) -> LNDWalletInstance:
        """Load or start an LND wallet instance.

        Args:
            seed: The aezeed mnemonic seed phrase
            tor_enabled: Per-wallet Tor override. None = use global setting.
            zero_conf: Per-wallet zero-conf monitoring. None = disabled.
        """
        wallet_key = seed_to_wallet_key(seed)
        # Return existing if already loaded (fast path, no lock needed)
        if wallet_key in self.wallets:
            return self.wallets[wallet_key]
        # Get or create per-wallet lock to prevent concurrent load attempts
        if wallet_key not in self._wallet_locks:
            self._wallet_locks[wallet_key] = asyncio.Lock()
        async with self._wallet_locks[wallet_key]:
            # Check again inside lock (another coroutine may have loaded it)
            if wallet_key in self.wallets:
                return self.wallets[wallet_key]
            return await self._start_wallet(seed, wallet_key, tor_enabled=tor_enabled, zero_conf=zero_conf)

    async def _start_wallet(self, seed: str, wallet_key: str, tor_enabled: bool | None = None, zero_conf: bool | None = None) -> LNDWalletInstance:
        """Internal: actually start the LND wallet instance (called under lock)."""
        # Allocate ports (includes Tor ports)
        ports = await self.port_manager.allocate(wallet_key)
        grpc_port = ports["grpc"]
        rest_port = ports["rest"]
        p2p_port = ports["p2p"]
        data_dir = self._get_wallet_dir(wallet_key)
        # Start Tor process if available (hybrid mode)
        # Per-wallet setting overrides global; None = use global default
        tor_proc = None
        if tor_enabled is None:
            tor_enabled = self.TOR_ENABLED
        tor_onion_hostname = ""
        if tor_enabled:
            tor_proc = TorProcess(
                data_dir=data_dir,
                socks_port=ports["tor_socks"],
                control_port=ports["tor_control"],
                p2p_port=p2p_port,
            )
            try:
                tor_bootstrapped = await tor_proc.start()
                if not tor_bootstrapped:
                    logger.warning(f"Tor bootstrap failed for wallet {wallet_key}, starting without Tor")
                    await tor_proc.stop()
                    tor_proc = None
                    tor_enabled = False
                else:
                    tor_onion_hostname = tor_proc.get_onion_hostname()
                    if tor_onion_hostname:
                        logger.info(f"Tor hidden service ready: {tor_onion_hostname}:{p2p_port}")
                    else:
                        logger.warning(f"Tor started but no .onion hostname found for wallet {wallet_key}")
            except Exception:
                logger.warning(f"Failed to start Tor for wallet {wallet_key}, continuing without Tor")
                tor_proc = None
                tor_enabled = False
        # Start LND process (no --tor.* flags; onion service is managed by TorProcess)
        lnd_proc = LNDProcess(
            lnd_binary=self.lnd_binary_path,
            data_dir=data_dir,
            network=self.LND_NETWORK,
            grpc_port=grpc_port,
            rest_port=rest_port,
            p2p_port=p2p_port,
            neutrino_peers=self.NEUTRINO_PEERS,
            extra_args=self.LND_EXTRA_ARGS,
            debug=self.VERBOSE,
            external_ip=self.EXTERNAL_IP,
            tor_onion_hostname=tor_onion_hostname,
        )
        await lnd_proc.start()
        if not await lnd_proc.wait_for_ready():
            await lnd_proc.stop()
            if tor_proc:
                await tor_proc.stop()
            raise Exception("LND failed to start")
        # Create gRPC client
        client = LNDGrpcClient(
            host="localhost",
            port=grpc_port,
            tls_cert_path=lnd_proc.tls_cert_path,
            macaroon_path=lnd_proc.macaroon_path,
        )
        # Init or unlock wallet with retry (LND may not be ready immediately after port opens)
        wallet_db_exists = os.path.exists(lnd_proc.wallet_db_path)
        await client.connect_unlocker()
        try:
            await self._unlock_or_init_with_retry(
                client, lnd_proc, wallet_key, wallet_db_exists, seed
            )
        except Exception:
            if tor_proc:
                await tor_proc.stop()
            raise
        # Wait for LND to be fully operational after unlock/init
        await self._wait_for_macaroon(lnd_proc, timeout=60)
        await client.connect()
        info = await self._wait_for_getinfo(client, timeout=60)
        # Create wallet instance
        wallet_inst = LNDWalletInstance(
            seed=seed,
            wallet_key=wallet_key,
            process=lnd_proc,
            grpc_client=client,
            grpc_port=grpc_port,
            rest_port=rest_port,
            p2p_port=p2p_port,
            data_dir=data_dir,
            identity_pubkey=info.identity_pubkey if info else None,
            synced_to_chain=info.synced_to_chain if info else False,
            tor_process=tor_proc,
            uris=list(info.uris) if info else [],
        )
        # Start process monitor and event subscriptions
        lnd_proc.start_monitor()
        self._start_event_subscriptions(wallet_inst)
        # Register wallet
        self.wallets[wallet_key] = wallet_inst
        self.wallets_updates[wallet_key] = deque(maxlen=self.POLLING_CAP)
        # Restore persisted request_addresses for on-chain payment tracking
        wallet_inst.request_addresses = self._load_request_addresses(wallet_key)
        # Start ElectrumX monitor for zero-conf detection if enabled
        if zero_conf:
            _, _, ElectrumXServerModel = self._get_request_db(wallet_key)
            # Height getter: returns LND's cached block height, or 0 if not synced.
            # Returns 0 until LND is fully synced, so we don't reject ElectrumX
            # servers based on height comparison before LND catches up.
            def get_height():
                inst = self.wallets.get(wallet_key)
                if inst and inst.synced_to_chain:
                    return inst.block_height
                return 0

            tor_port = None
            if wallet_inst.tor_process and wallet_inst.tor_process.socks_port:
                tor_port = wallet_inst.tor_process.socks_port
            monitor = ElectrumXMonitor(
                network=self.LND_NETWORK,
                on_payment_detected=lambda **kwargs: self._on_electrumx_payment(wallet_key, **kwargs),
                tor_socks_port=tor_port,
                get_our_height=get_height,
                server_db=ElectrumXServerModel,
            )
            if await monitor.start():
                wallet_inst.electrumx_monitor = monitor
                # Subscribe to any existing watched addresses
                for rhash, info in wallet_inst.request_addresses.items():
                    await monitor.watch_address(info["address"], rhash, info["amount_sat"])
                logger.info(f"Zero-conf monitoring enabled for wallet {wallet_key}")
            else:
                logger.warning(f"Zero-conf monitoring unavailable for wallet {wallet_key} (no ElectrumX servers)")
        # Persist seed map so this wallet auto-starts on next daemon boot
        self._save_seed_map()
        logger.info(
            f"Wallet loaded: {wallet_key} "
            f"(pubkey={wallet_inst.identity_pubkey}, synced={wallet_inst.synced_to_chain}, "
            f"tor={'yes' if tor_proc else 'no'}, zero_conf={'yes' if wallet_inst.electrumx_monitor else 'no'}, "
            f"uris={wallet_inst.uris})"
        )
        return wallet_inst

    async def _unlock_or_init_with_retry(
        self, client: LNDGrpcClient, lnd_proc: LNDProcess,
        wallet_key: str, wallet_db_exists: bool, seed: str,
        max_retries: int = 10, retry_delay: float = 2.0,
    ):
        """Unlock or initialize the wallet with retry for transient gRPC errors.

        LND's WalletUnlocker service may not be ready immediately after the gRPC
        port starts accepting connections. This method retries on "waiting to start"
        and similar transient errors.
        """
        for attempt in range(max_retries):
            try:
                if wallet_db_exists:
                    logger.info(f"Unlocking existing wallet: {wallet_key} (attempt {attempt + 1})")
                    await client.unlock_wallet(self.LND_WALLET_PASSWORD)
                else:
                    logger.info(f"Initializing new wallet: {wallet_key} (attempt {attempt + 1})")
                    seed_words = seed.strip().split()
                    await client.init_wallet(self.LND_WALLET_PASSWORD, seed_words)
                return  # success
            except grpc.aio.AioRpcError as e:
                error_detail = (e.details() or "").lower()
                # "wallet already unlocked" is fine — means another call already did it
                if "wallet already unlocked" in error_detail:
                    logger.info(f"Wallet {wallet_key} already unlocked, proceeding")
                    return
                # Transient: LND gRPC is up but services aren't ready yet
                if "waiting to start" in error_detail or "rpc services not available" in error_detail:
                    if attempt < max_retries - 1:
                        logger.debug(
                            f"LND not ready for wallet ops yet, retrying in {retry_delay}s "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        await asyncio.sleep(retry_delay)
                        # Reconnect the unlocker in case the channel broke
                        try:
                            await client.connect_unlocker()
                        except Exception:
                            pass
                        continue
                # Non-transient error
                logger.error(
                    f"Failed to {'unlock' if wallet_db_exists else 'init'} wallet {wallet_key}: "
                    f"code={e.code()}, details={e.details()}"
                )
                await lnd_proc.stop()
                raise Exception(
                    f"Wallet {'unlock' if wallet_db_exists else 'init'} failed: {e.details()}"
                )
        # Exhausted retries
        logger.error(f"Wallet {wallet_key}: exhausted {max_retries} unlock/init retries")
        await lnd_proc.stop()
        raise Exception("LND wallet unlock/init timed out - RPC services never became available")

    async def _wait_for_macaroon(self, lnd_proc: LNDProcess, timeout: int = 60):
        """Wait for the admin macaroon file to appear after wallet init."""
        for _ in range(timeout * 2):
            if os.path.exists(lnd_proc.macaroon_path):
                return
            await asyncio.sleep(0.5)
        raise Exception("Macaroon file not created within timeout")

    async def _wait_for_getinfo(self, client: LNDGrpcClient, timeout: int = 60):
        """Wait for GetInfo to succeed (LND fully operational)."""
        for _ in range(timeout * 2):
            try:
                return await client.get_info()
            except grpc.aio.AioRpcError:
                await asyncio.sleep(0.5)
        raise Exception("LND did not become operational within timeout")

    def is_still_syncing(self, wallet_key: str | None = None) -> bool:
        """Check if LND is still syncing the blockchain.

        Args:
            wallet_key: Optional wallet to check. If None, checks daemon-level sync.

        Returns:
            True if still syncing
        """
        if self.NO_SYNC_WAIT:
            return False
        if wallet_key and wallet_key in self.wallets:
            return not self.wallets[wallet_key].synced_to_chain
        # If no wallets loaded, the daemon itself is ready (nothing to sync)
        if not self.wallets:
            return False
        # Otherwise, check if any wallet is synced
        return not any(w.synced_to_chain for w in self.wallets.values())

    # -------------------------------------------------------------------------
    # Event subscription system
    # -------------------------------------------------------------------------

    MAX_SUBSCRIPTION_RETRIES = 20
    INITIAL_BACKOFF = 2  # seconds
    MAX_BACKOFF = 300    # 5 minutes

    def _start_event_subscriptions(self, wallet_inst: LNDWalletInstance):
        """Start streaming gRPC subscriptions for a wallet instance."""
        client = wallet_inst.grpc_client
        wk = wallet_inst.wallet_key
        wallet_inst.event_tasks = [
            asyncio.create_task(self._subscribe_invoices(client, wk)),
            asyncio.create_task(self._subscribe_transactions(client, wk)),
            asyncio.create_task(self._subscribe_block_epochs(client, wk)),
            asyncio.create_task(self._subscribe_channel_events(client, wk)),
            asyncio.create_task(self._sync_status_poller(client, wk)),
            asyncio.create_task(self._poll_onchain_payments(client, wk)),
        ]
        # Name tasks for health monitoring
        names = ["invoices", "transactions", "blocks", "channels", "sync", "poll_onchain"]
        for task, name in zip(wallet_inst.event_tasks, names):
            task.set_name(f"{wk}:{name}")
        # Start health monitor
        wallet_inst.event_tasks.append(
            asyncio.create_task(self._task_health_monitor(wallet_inst))
        )

    async def _task_health_monitor(self, wallet_inst: LNDWalletInstance):
        """Monitor event subscription tasks and log if any die unexpectedly.

        Checks every 30 seconds. If a critical task (invoices, transactions,
        blocks) has ended, logs an error so operators can investigate.
        """
        critical_names = {"invoices", "transactions", "blocks"}
        while self.running:
            try:
                await asyncio.sleep(30)
                if wallet_inst.wallet_key not in self.wallets:
                    return
                for task in wallet_inst.event_tasks:
                    if task is asyncio.current_task():
                        continue
                    if task.done() and not task.cancelled():
                        name = task.get_name()
                        exc = task.exception() if not task.cancelled() else None
                        # Check if this is a critical subscription
                        short_name = name.split(":")[-1] if ":" in name else name
                        if short_name in critical_names:
                            logger.error(
                                f"Critical subscription task '{name}' died"
                                f"{f': {exc}' if exc else ' (exhausted retries)'}"
                            )
                        elif exc:
                            logger.warning(f"Background task '{name}' ended with error: {exc}")
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _subscribe_invoices(self, client: LNDGrpcClient, wallet_key: str):
        """Subscribe to invoice state changes, dispatch new_payment events.

        Also performs a one-time catch-up scan for invoices that settled while
        the daemon was offline (SubscribeInvoices only delivers live events).
        """
        # Catch-up: check for recently settled invoices we may have missed
        try:
            await self._catchup_settled_invoices(client, wallet_key)
        except Exception:
            logger.error(f"Invoice catchup failed:\n{traceback.format_exc()}")
        # Now subscribe to live events
        logger.info(f"Invoice subscription started for wallet {wallet_key}")
        retries = 0
        while self.running:
            try:
                async for invoice in client.subscribe_invoices():
                    logger.info(
                        f"Invoice event: wallet={wallet_key}, state={invoice.state}, "
                        f"rhash={invoice.r_hash.hex()[:16]}..."
                    )
                    if invoice.state == INVOICE_SETTLED:
                        data = {
                            "event": "new_payment",
                            "address": invoice.r_hash.hex(),
                            "status": PR_PAID,
                            "status_str": PR_STATUS_STR[PR_PAID],
                            "tx_hashes": [invoice.r_hash.hex()],
                            "sent_amount": format_satoshis(invoice.amt_paid_sat),
                        }
                        logger.info(f"Dispatching new_payment for {invoice.r_hash.hex()[:16]}...")
                        await self._dispatch_event(data, wallet_key)
            except grpc.aio.AioRpcError as e:
                if not self.running:
                    break
                retries += 1
                backoff = min(self.INITIAL_BACKOFF * (2 ** (retries - 1)), self.MAX_BACKOFF)
                logger.warning(f"Invoice subscription error ({retries}/{self.MAX_SUBSCRIPTION_RETRIES}): {e.code()}, retry in {backoff}s")
                if retries >= self.MAX_SUBSCRIPTION_RETRIES:
                    logger.error(f"Invoice subscription for {wallet_key} exceeded max retries, giving up")
                    break
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                break
            except Exception:
                if not self.running:
                    break
                retries += 1
                backoff = min(self.INITIAL_BACKOFF * (2 ** (retries - 1)), self.MAX_BACKOFF)
                logger.warning(f"Invoice subscription error ({retries}/{self.MAX_SUBSCRIPTION_RETRIES}):\n{traceback.format_exc()}")
                if retries >= self.MAX_SUBSCRIPTION_RETRIES:
                    logger.error(f"Invoice subscription for {wallet_key} exceeded max retries, giving up")
                    break
                await asyncio.sleep(backoff)

    async def _catchup_settled_invoices(self, client: LNDGrpcClient, wallet_key: str):
        """Dispatch new_payment events for invoices that settled while daemon was offline.

        Checks all settled invoices from LND and dispatches events for any that
        settled recently (within last 24 hours). This handles the case where
        a payment arrived while the daemon was restarting.
        """
        import time

        cutoff = int(time.time()) - 86400  # last 24 hours
        invoices = await client.list_invoices()
        settled_count = 0
        for inv in invoices:
            if inv.state == INVOICE_SETTLED and inv.settle_date > cutoff:
                data = {
                    "event": "new_payment",
                    "address": inv.r_hash.hex(),
                    "status": PR_PAID,
                    "status_str": PR_STATUS_STR[PR_PAID],
                    "tx_hashes": [inv.r_hash.hex()],
                    "sent_amount": format_satoshis(inv.amt_paid_sat),
                }
                await self._dispatch_event(data, wallet_key)
                settled_count += 1
        if settled_count:
            logger.info(f"Catchup: dispatched {settled_count} settled invoice event(s) for wallet {wallet_key}")

    async def _subscribe_transactions(self, client: LNDGrpcClient, wallet_key: str):
        """Subscribe to on-chain transaction updates.

        When a transaction is received to a tracked payment address,
        dispatches a new_payment event so the worker's check_pending detects it.
        """
        retries = 0
        while self.running:
            try:
                async for tx in client.subscribe_transactions():
                    retries = 0  # reset on successful event
                    logger.info(
                        f"SubscribeTransactions event: wallet={wallet_key}, "
                        f"tx={tx.tx_hash[:16]}..., confs={tx.num_confirmations}, "
                        f"amount={tx.amount}, dest_addrs={list(tx.dest_addresses)[:3]}"
                    )
                    data = {
                        "event": "new_transaction",
                        "tx": tx.tx_hash,
                    }
                    await self._dispatch_event(data, wallet_key)
                    await self._check_onchain_payment(client, wallet_key, tx)
            except grpc.aio.AioRpcError as e:
                if not self.running:
                    break
                retries += 1
                backoff = min(self.INITIAL_BACKOFF * (2 ** (retries - 1)), self.MAX_BACKOFF)
                logger.warning(f"Transaction subscription error ({retries}/{self.MAX_SUBSCRIPTION_RETRIES}): {e}, retry in {backoff}s")
                if retries >= self.MAX_SUBSCRIPTION_RETRIES:
                    logger.error(f"Transaction subscription for {wallet_key} exceeded max retries")
                    break
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                break
            except Exception:
                if not self.running:
                    break
                retries += 1
                backoff = min(self.INITIAL_BACKOFF * (2 ** (retries - 1)), self.MAX_BACKOFF)
                logger.warning(f"Transaction subscription error ({retries}/{self.MAX_SUBSCRIPTION_RETRIES}):\n{traceback.format_exc()}")
                if retries >= self.MAX_SUBSCRIPTION_RETRIES:
                    logger.error(f"Transaction subscription for {wallet_key} exceeded max retries")
                    break
                await asyncio.sleep(backoff)

    async def _check_onchain_payment(self, client: LNDGrpcClient, wallet_key: str, tx):
        """Check if a transaction pays to any tracked payment request address.

        If it does, dispatch a new_payment event so the worker detects it.
        """
        if wallet_key not in self.wallets:
            return
        wallet_inst = self.wallets[wallet_key]
        async with wallet_inst.request_lock:
            if not wallet_inst.request_addresses:
                return
            # Snapshot under lock to avoid iteration during concurrent modification
            addr_to_rhash = {
                info["address"]: rhash
                for rhash, info in wallet_inst.request_addresses.items()
            }
            addr_to_info = {
                info["address"]: info
                for info in wallet_inst.request_addresses.values()
            }
        if not addr_to_rhash:
            return
        # Check transaction outputs against tracked addresses
        # Also check output_details for more accurate per-output matching
        matched_addrs = set()
        for addr in tx.dest_addresses:
            if addr in addr_to_rhash:
                matched_addrs.add(addr)
        for out in getattr(tx, "output_details", []):
            addr = getattr(out, "address", "")
            if addr in addr_to_rhash:
                matched_addrs.add(addr)
        for addr in matched_addrs:
            rhash = addr_to_rhash[addr]
            info = addr_to_info[addr]
            try:
                received, _ = await self._check_address_received(client, addr)
                logger.info(
                    f"On-chain payment detected: addr={addr[:20]}..., "
                    f"received={received} sats (need {info['amount_sat']}), tx={tx.tx_hash[:16]}..."
                )
                if received >= info["amount_sat"]:
                    data = {
                        "event": "new_payment",
                        "address": rhash,
                        "status": PR_PAID,
                        "status_str": "Paid",
                        "tx_hashes": [tx.tx_hash],
                        "sent_amount": format_satoshis(received),
                    }
                    await self._dispatch_event(data, wallet_key)
            except Exception:
                logger.debug(f"Failed to check on-chain payment: {traceback.format_exc()}")

    async def _subscribe_block_epochs(self, client: LNDGrpcClient, wallet_key: str):
        """Subscribe to new block notifications (global event)."""
        retries = 0
        while self.running:
            try:
                async for block_epoch in client.register_block_epoch():
                    retries = 0
                    data = {
                        "event": "new_block",
                        "height": block_epoch.height,
                    }
                    for wk in self.wallets:
                        if self.POLLING_CAP > 0 and wk in self.wallets_updates:
                            self.wallets_updates[wk].append(data)
                    await self.notify_websockets(data, None)
            except grpc.aio.AioRpcError:
                if not self.running:
                    break
                retries += 1
                backoff = min(self.INITIAL_BACKOFF * (2 ** (retries - 1)), self.MAX_BACKOFF)
                logger.warning(f"Block epoch subscription error ({retries}/{self.MAX_SUBSCRIPTION_RETRIES}), retry in {backoff}s")
                if retries >= self.MAX_SUBSCRIPTION_RETRIES:
                    logger.error(f"Block epoch subscription for {wallet_key} exceeded max retries")
                    break
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                break
            except Exception:
                if not self.running:
                    break
                retries += 1
                backoff = min(self.INITIAL_BACKOFF * (2 ** (retries - 1)), self.MAX_BACKOFF)
                logger.warning(f"Block epoch subscription error ({retries}/{self.MAX_SUBSCRIPTION_RETRIES}):\n{traceback.format_exc()}")
                if retries >= self.MAX_SUBSCRIPTION_RETRIES:
                    logger.error(f"Block epoch subscription for {wallet_key} exceeded max retries")
                    break
                await asyncio.sleep(backoff)

    async def _subscribe_channel_events(self, client: LNDGrpcClient, wallet_key: str):
        """Subscribe to channel state changes (logged for diagnostics)."""
        retries = 0
        while self.running:
            try:
                async for event in client.subscribe_channel_events():
                    retries = 0
                    logger.debug(f"Channel event for {wallet_key}: type={event.type}")
            except grpc.aio.AioRpcError:
                if not self.running:
                    break
                retries += 1
                backoff = min(self.INITIAL_BACKOFF * (2 ** (retries - 1)), self.MAX_BACKOFF)
                if retries >= self.MAX_SUBSCRIPTION_RETRIES:
                    break
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                break
            except Exception:
                if not self.running:
                    break
                retries += 1
                backoff = min(self.INITIAL_BACKOFF * (2 ** (retries - 1)), self.MAX_BACKOFF)
                if retries >= self.MAX_SUBSCRIPTION_RETRIES:
                    break
                await asyncio.sleep(backoff)

    async def _poll_onchain_payments(self, client: LNDGrpcClient, wallet_key: str):
        """Periodically poll watched addresses for on-chain payments.

        LND in neutrino mode only fires SubscribeTransactions when a
        transaction is confirmed in a block (not when it enters the mempool).
        This poller runs every 15 seconds as a safety net to detect confirmed
        payments that SubscribeTransactions may have missed due to timing.

        NOTE: Unconfirmed (mempool) transaction detection is a known limitation
        of neutrino mode. Unlike Electrum (which gets instant mempool push
        notifications from ElectrumX servers), neutrino only learns about
        transactions through compact block filters when blocks arrive.
        """
        while self.running:
            try:
                await asyncio.sleep(15)
                if wallet_key not in self.wallets:
                    return
                wallet_inst = self.wallets[wallet_key]
                # Snapshot under lock
                async with wallet_inst.request_lock:
                    items = list(wallet_inst.request_addresses.items())
                if not items:
                    continue
                for rhash, info in items:
                    address = info["address"]
                    amount_sat = info["amount_sat"]
                    try:
                        received, tx_hashes = await self._check_address_received(client, address)
                        if received >= amount_sat:
                            data = {
                                "event": "new_payment",
                                "address": rhash,
                                "status": PR_PAID,
                                "status_str": "Paid",
                                "tx_hashes": tx_hashes,
                                "sent_amount": format_satoshis(received),
                            }
                            await self._dispatch_event(data, wallet_key)
                            async with wallet_inst.request_lock:
                                wallet_inst.request_addresses.pop(rhash, None)
                    except Exception:
                        pass
            except asyncio.CancelledError:
                break
            except Exception:
                if not self.running:
                    break
                await asyncio.sleep(15)

    async def _enable_zero_conf(self, wallet_inst: LNDWalletInstance):
        """Hot-enable zero-conf monitoring on an already-loaded wallet."""
        wallet_key = wallet_inst.wallet_key
        _, _, ElectrumXServerModel = self._get_request_db(wallet_key)

        def get_height():
            inst = self.wallets.get(wallet_key)
            if inst and inst.synced_to_chain:
                return inst.block_height
            return 0

        tor_port = None
        if wallet_inst.tor_process and wallet_inst.tor_process.socks_port:
            tor_port = wallet_inst.tor_process.socks_port
        monitor = ElectrumXMonitor(
            network=self.LND_NETWORK,
            on_payment_detected=lambda **kwargs: self._on_electrumx_payment(wallet_key, **kwargs),
            tor_socks_port=tor_port,
            get_our_height=get_height,
            server_db=ElectrumXServerModel,
        )
        if await monitor.start():
            wallet_inst.electrumx_monitor = monitor
            for rhash, info in wallet_inst.request_addresses.items():
                await monitor.watch_address(info["address"], rhash, info["amount_sat"])
            logger.info(f"Zero-conf monitoring enabled for wallet {wallet_key}")
            self._save_seed_map()
        else:
            logger.warning(f"Zero-conf monitoring unavailable for wallet {wallet_key}")

    async def _on_electrumx_payment(self, wallet_key: str, address: str, rhash: str,
                                     amount_sat: int, tx_hashes: list, confirmed: bool):
        """Callback from ElectrumXMonitor when a payment is detected via mempool."""
        # Dedup: skip if already removed from request_addresses (detected by another path)
        if wallet_key in self.wallets:
            wallet_inst = self.wallets[wallet_key]
            async with wallet_inst.request_lock:
                if rhash not in wallet_inst.request_addresses:
                    return
                wallet_inst.request_addresses.pop(rhash, None)
        status = PR_PAID if confirmed else PR_UNCONFIRMED
        data = {
            "event": "new_payment",
            "address": rhash,
            "status": status,
            "status_str": PR_STATUS_STR.get(status, "Unknown"),
            "tx_hashes": tx_hashes,
            "sent_amount": format_satoshis(amount_sat),
        }
        logger.info(
            f"ElectrumX payment detected: wallet={wallet_key}, addr={address[:20]}..., "
            f"amount={amount_sat} sats, confirmed={confirmed}"
        )
        await self._dispatch_event(data, wallet_key)

    async def _sync_status_poller(self, client: LNDGrpcClient, wallet_key: str):
        """Periodically check sync status and update URIs until fully synced."""
        while self.running:
            try:
                info = await client.get_info()
                if wallet_key in self.wallets:
                    self.wallets[wallet_key].synced_to_chain = info.synced_to_chain
                    self.wallets[wallet_key].block_height = info.block_height
                    # Update URIs (includes onion addresses once Tor is ready)
                    if info.uris:
                        self.wallets[wallet_key].uris = list(info.uris)
                    if info.synced_to_chain:
                        logger.info(f"Wallet {wallet_key} synced to chain (height={info.block_height})")
                        return  # stop polling once synced
            except Exception:
                pass
            await asyncio.sleep(5)

    async def _dispatch_event(self, data: dict, wallet_key: str):
        """Send event to websocket clients and polling queue."""
        ws_count = len(self.app["websockets"])
        logger.debug(f"Dispatching event {data.get('event')} to {ws_count} websocket(s)")
        result = await self.notify_websockets(data, wallet_key)
        if self.POLLING_CAP > 0 and wallet_key in self.wallets_updates:
            self.wallets_updates[wallet_key].append(data)

    # -------------------------------------------------------------------------
    # Request execution (override from BaseDaemon)
    # -------------------------------------------------------------------------

    async def execute_method(self, req_id, req_method, xpub, contract, extra_params, req_args, req_kwargs):
        """Execute an RPC method with wallet context.

        Loads the wallet if needed, waits for sync if required,
        then dispatches to the appropriate @rpc method.
        """
        wallet_key = self._get_wallet_key(xpub)
        # Find the method
        if req_method not in self.supported_methods:
            return JsonResponse(code=-32601, error="Procedure not found", id=req_id).send()
        method_func = self.supported_methods[req_method]
        # Load wallet if xpub provided
        wallet_inst = None
        if xpub:
            # close_wallet should not trigger load_wallet — just use existing or clean up
            if req_method == "close_wallet":
                wallet_key = self._get_wallet_key(xpub)
            else:
                # Extract per-wallet settings from extra_params
                wallet_tor = extra_params.get("tor_enabled") if extra_params else None
                if wallet_tor is not None:
                    wallet_tor = str(wallet_tor).lower() in ("true", "1", "yes")
                wallet_zero_conf = extra_params.get("zero_conf_monitoring") if extra_params else None
                if wallet_zero_conf is not None:
                    wallet_zero_conf = str(wallet_zero_conf).lower() in ("true", "1", "yes")
                try:
                    wallet_inst = await self.load_wallet(xpub, tor_enabled=wallet_tor, zero_conf=wallet_zero_conf)
                    wallet_key = wallet_inst.wallet_key
                    # Hot-enable zero-conf monitoring if toggled on after wallet load
                    if wallet_zero_conf and not wallet_inst.electrumx_monitor:
                        await self._enable_zero_conf(wallet_inst)
                    # Wait for sync if method requires network
                    if method_func.requires_network and not self.NO_SYNC_WAIT:
                        await self._wait_for_wallet_sync(wallet_key)
                except Exception as e:
                    if method_func.requires_wallet:
                        error_msg = str(e)
                        return JsonResponse(
                            code=self.get_error_code(error_msg, fallback_code=-32005),
                            error=error_msg,
                            id=req_id,
                        ).send()
        # Check wallet requirement
        if method_func.requires_wallet and not wallet_key:
            return JsonResponse(code=-32000, error="Wallet not loaded", id=req_id).send()
        # Execute the method
        try:
            exec_method = functools.partial(method_func, wallet=wallet_key)
            result = exec_method(*req_args, **req_kwargs)
            if inspect.isawaitable(result):
                result = await result
            return JsonResponse(result=result, id=req_id).send()
        except Exception as e:
            if not extra_params.get("quiet_mode"):
                logger.error(traceback.format_exc())
            # Extract clean error message from gRPC errors
            if isinstance(e, grpc.aio.AioRpcError):
                error_msg = e.details() or str(e.code())
            else:
                error_msg = str(e)
            return JsonResponse(
                code=self.get_error_code(error_msg),
                error=error_msg,
                id=req_id,
            ).send()

    async def _wait_for_wallet_sync(self, wallet_key: str, timeout: int = 300):
        """Wait for a specific wallet to sync to chain."""
        for _ in range(timeout * 2):
            if wallet_key in self.wallets and self.wallets[wallet_key].synced_to_chain:
                return
            if self.NO_SYNC_WAIT:
                return
            await asyncio.sleep(0.5)

    def _get_client(self, wallet_key: str) -> LNDGrpcClient:
        """Get the gRPC client for a wallet, raising if not found."""
        if wallet_key not in self.wallets:
            raise Exception("Wallet not loaded")
        return self.wallets[wallet_key].grpc_client

    # -------------------------------------------------------------------------
    # RPC Methods - Core info and status
    # -------------------------------------------------------------------------

    async def _get_routing_stats(self, client: LNDGrpcClient) -> dict:
        """Get routing statistics (total routed amount and fees collected)."""
        try:
            events = await client.forwarding_history()
            total_routed_msat = sum(e.amt_in_msat for e in events)
            total_fees_msat = sum(e.fee_msat for e in events)
            total_routed_sat = total_routed_msat // 1000
            total_fees_sat = total_fees_msat // 1000
            return {
                "total_payments_routed": len(events),
                "total_amount_routed_sats": total_routed_sat,
                "total_amount_routed_btc": format_satoshis(total_routed_sat),
                "total_fees_collected_sats": total_fees_sat,
                "total_fees_collected_btc": format_satoshis(total_fees_sat),
            }
        except Exception:
            return {
                "total_payments_routed": 0,
                "total_amount_routed_sats": 0,
                "total_amount_routed_btc": "0",
                "total_fees_collected_sats": 0,
                "total_fees_collected_btc": "0",
            }

    @rpc
    async def getinfo(self, wallet=None):
        """Get daemon and node information including URIs and Tor status."""
        if wallet and wallet in self.wallets:
            client = self._get_client(wallet)
            info = await client.get_info()
            p2p_port = self.wallets[wallet].p2p_port
            # Build complete list of node addresses from all sources
            uris = self._build_node_uris(
                info.identity_pubkey, p2p_port, list(info.uris) if info.uris else []
            )
            # Update cached URIs
            self.wallets[wallet].uris = uris
            clearnet_uris = [u for u in uris if ".onion:" not in u]
            onion_uris = [u for u in uris if ".onion:" in u]
            # Compute sync progress from best_header_timestamp
            import time

            sync_progress = ""
            if not info.synced_to_chain and info.best_header_timestamp > 0:
                from datetime import datetime, timezone

                header_time = datetime.fromtimestamp(info.best_header_timestamp, tz=timezone.utc)
                now = datetime.now(tz=timezone.utc)
                # Rough progress: signet started ~Aug 2020, so estimate based on time range
                total_span = (now - datetime(2020, 8, 1, tzinfo=timezone.utc)).total_seconds()
                synced_span = (header_time - datetime(2020, 8, 1, tzinfo=timezone.utc)).total_seconds()
                if total_span > 0 and synced_span > 0:
                    pct = min(99.9, max(0, (synced_span / total_span) * 100))
                    sync_progress = f"{pct:.1f}% (headers up to {header_time.strftime('%Y-%m-%d %H:%M')} UTC)"
            return {
                "version": info.version,
                "identity_pubkey": info.identity_pubkey,
                "alias": info.alias,
                "num_active_channels": info.num_active_channels,
                "num_inactive_channels": info.num_inactive_channels,
                "num_pending_channels": info.num_pending_channels,
                "num_peers": info.num_peers,
                "block_height": info.block_height,
                "block_hash": info.block_hash,
                "synced_to_chain": info.synced_to_chain,
                "synced_to_graph": info.synced_to_graph,
                "synchronized": info.synced_to_chain,
                "total_wallets": len(self.wallets),
                "server_height": info.block_height,
                "blockchain_height": info.block_height,
                "best_header_timestamp": info.best_header_timestamp,
                "sync_progress": sync_progress,
                "uris": uris,
                "clearnet_uri": clearnet_uris[0] if clearnet_uris else "",
                "onion_uri": onion_uris[0] if onion_uris else "",
                "tor_enabled": self.wallets[wallet].tor_process is not None,
                "zero_conf_monitoring": self.wallets[wallet].electrumx_monitor is not None,
                "network": self.LND_NETWORK,
                **await self._get_routing_stats(client),
            }
        synced = not self.is_still_syncing()
        return {
            "version": self.LND_VERSION,
            "synchronized": synced,
            "synced_to_chain": synced,
            "synced_to_graph": synced,
            "total_wallets": len(self.wallets),
            "server_height": 0,
            "blockchain_height": 0,
            "block_height": 0,
            "tor_enabled": self.TOR_ENABLED,
            "network": self.LND_NETWORK,
        }

    @rpc
    async def help(self, func=None, wallet=None):
        """List available RPC methods or get help for a specific method."""
        if func is None:
            methods = sorted(self.supported_methods.keys())
            methods.extend(sorted(self.ALIASES.keys()))
            return methods
        if func in self.supported_methods:
            return get_function_header(func, self.supported_methods[func])
        if func in self.ALIASES and self.ALIASES[func] in self.supported_methods:
            return get_function_header(func, self.supported_methods[self.ALIASES[func]])
        raise Exception("Procedure not found")

    @rpc
    def validatekey(self, key, wallet=None, **kwargs):
        """Validate if a key is a valid 24-word aezeed mnemonic.

        Checks word count and verifies each word is in the aezeed wordlist.
        LND's aezeed uses the same BIP39 English wordlist (2048 words).

        Args:
            key: The seed phrase to validate

        Returns:
            True if valid, False otherwise
        """
        if not key or not isinstance(key, str):
            return False
        words = key.strip().split()
        if len(words) != AEZEED_WORD_COUNT:
            return False
        # Verify each word is in the aezeed/BIP39 wordlist
        wordlist = self._get_aezeed_wordlist()
        if wordlist:
            return all(w in wordlist for w in words)
        return True  # if we can't load wordlist, just check count

    def _get_aezeed_wordlist(self):
        """Load the BIP39/aezeed English wordlist.

        LND's aezeed cipher seed uses the standard BIP39 English wordlist.
        We cache it after first load.
        """
        if not hasattr(self, "_wordlist_cache"):
            import importlib.resources
            try:
                # Try to read from a bundled wordlist file
                wordlist_path = os.path.join(
                    os.path.dirname(__file__), "aezeed_wordlist.txt"
                )
                if os.path.exists(wordlist_path):
                    with open(wordlist_path) as f:
                        self._wordlist_cache = set(f.read().strip().split("\n"))
                else:
                    self._wordlist_cache = None
            except Exception:
                self._wordlist_cache = None
        return self._wordlist_cache

    @rpc
    async def make_seed(self, nbits=128, language="english", full_info=False, wallet=None):
        """Generate a new 24-word aezeed mnemonic seed.

        Starts a temporary LND instance to call GenSeed, then shuts it down.
        The seed can then be used to create a new wallet via load_wallet().

        Returns:
            str: Space-separated 24-word mnemonic seed phrase
        """
        import tempfile

        # Allocate temporary ports for the seed generation LND instance
        tmp_key = f"_seed_gen_{id(self)}"
        ports = await self.port_manager.allocate(tmp_key)
        tmp_dir = tempfile.mkdtemp(prefix="lnd-seedgen-")
        try:
            lnd_proc = LNDProcess(
                lnd_binary=self.lnd_binary_path,
                data_dir=tmp_dir,
                network=self.LND_NETWORK,
                grpc_port=ports["grpc"],
                rest_port=ports["rest"],
                p2p_port=ports["p2p"],
                neutrino_peers=self.NEUTRINO_PEERS,
                debug=self.VERBOSE,
            )
            await lnd_proc.start()
            if not await lnd_proc.wait_for_ready():
                raise Exception("Failed to start temporary LND for seed generation")
            # Connect to WalletUnlocker (no macaroon needed for GenSeed)
            client = LNDGrpcClient(
                host="localhost",
                port=ports["grpc"],
                tls_cert_path=lnd_proc.tls_cert_path,
                macaroon_path=lnd_proc.macaroon_path,
            )
            await client.connect_unlocker()
            seed_words = await client.gen_seed()
            return " ".join(seed_words)
        finally:
            # Clean up temporary LND instance
            try:
                await lnd_proc.stop(timeout=10)
            except Exception:
                pass
            await self.port_manager.release(tmp_key)
            # Remove temporary directory
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # RPC Methods - Wallet operations
    # -------------------------------------------------------------------------

    @rpc(requires_wallet=True)
    async def getbalance(self, wallet):
        """Get wallet balance: on-chain in confirmed/unconfirmed/unmatured,
        lightning channel funds in the lightning field.

        Raises an error if the wallet's LND instance is still syncing,
        matching Electrum's behavior of not returning balance until synced.

        Returns dict with confirmed, unconfirmed, unmatured, and lightning balances.
        """
        # Check sync status — report error while syncing so the UI shows the correct indicator
        if wallet in self.wallets and not self.wallets[wallet].synced_to_chain:
            if not self.NO_SYNC_WAIT:
                raise Exception("chain backend is still syncing")
        client = self._get_client(wallet)
        balance = await client.wallet_balance()
        # Get lightning balance: sum of local_balance across all non-closed channels
        lightning_balance = 0
        try:
            channels = await client.list_channels()
            for ch in channels:
                lightning_balance += ch.local_balance
        except Exception:
            pass  # if channel query fails, report 0
        return {
            "confirmed": format_satoshis(balance.confirmed_balance),
            "unconfirmed": format_satoshis(balance.unconfirmed_balance),
            "unmatured": format_satoshis(0),  # LND doesn't track immature coinbase
            "lightning": format_satoshis(lightning_balance),
        }

    @rpc(requires_wallet=True)
    async def getaddressbalance_wallet(self, address, wallet):
        """Get balance for a specific address.

        Args:
            address: Bitcoin address to check

        Returns:
            Dict with confirmed, unconfirmed, unmatured balances
        """
        client = self._get_client(wallet)
        utxos = await client.list_unspent()
        confirmed = 0
        unconfirmed = 0
        for utxo in utxos:
            if utxo.address == address:
                if utxo.confirmations > 0:
                    confirmed += utxo.amount_sat
                else:
                    unconfirmed += utxo.amount_sat
        return {
            "confirmed": format_satoshis(confirmed),
            "unconfirmed": format_satoshis(unconfirmed),
            "unmatured": format_satoshis(0),
        }

    @rpc(requires_wallet=True)
    async def createnewaddress(self, wallet):
        """Generate a new on-chain receiving address.

        Returns:
            New bech32 (SegWit) address
        """
        client = self._get_client(wallet)
        return await client.new_address(addr_type=0)  # WITNESS_PUBKEY_HASH

    @rpc(requires_wallet=True)
    async def listaddresses(self, wallet):
        """List addresses that have received funds.

        Returns:
            List of address strings
        """
        client = self._get_client(wallet)
        utxos = await client.list_unspent()
        addresses = list({utxo.address for utxo in utxos if utxo.address})
        return addresses

    @rpc(requires_wallet=True)
    def getseed(self, wallet):
        """Return the stored seed phrase for this wallet.

        Returns:
            The mnemonic seed phrase string
        """
        if wallet not in self.wallets:
            raise Exception("Wallet not loaded")
        return self.wallets[wallet].seed

    @rpc(requires_wallet=True)
    def getlndinfo(self, wallet):
        """Return LND gRPC connection info for this wallet.

        Reads the wallet's tls.cert and admin.macaroon from disk and returns
        them base64-encoded so callers in other containers (or on the host)
        can connect directly to this wallet's LND gRPC interface.

        Returns:
            Dict with host, grpc_port, network, tls_cert (b64), macaroon (b64).
        """
        import base64

        if wallet not in self.wallets:
            raise Exception("Wallet not loaded")
        inst = self.wallets[wallet]
        proc = inst.process
        with open(proc.tls_cert_path, "rb") as f:
            tls_cert_b64 = base64.b64encode(f.read()).decode("ascii")
        with open(proc.macaroon_path, "rb") as f:
            macaroon_b64 = base64.b64encode(f.read()).decode("ascii")
        # LND binds to 127.0.0.1 inside this container; the cert SANs include
        # both 127.0.0.1 and localhost (see lnd_process.py --tlsextraip /
        # --tlsextradomain). Override via BTCLND_GRPC_PUBLIC_HOST when callers
        # reach the daemon over the docker network or a different address.
        return {
            "host": self.GRPC_PUBLIC_HOST,
            "grpc_port": inst.grpc_port,
            "network": self.LND_NETWORK,
            "tls_cert": tls_cert_b64,
            "macaroon": macaroon_b64,
        }

    @rpc(requires_wallet=True)
    def get_updates(self, wallet):
        """Get queued event updates for this wallet (polling mode).

        Returns:
            List of event dicts since last call
        """
        updates = self.wallets_updates.get(wallet, deque())
        self.wallets_updates[wallet] = deque(maxlen=self.POLLING_CAP)
        return list(updates)

    @rpc
    async def close_wallet(self, key=None, wallet=None):
        """Close and stop an LND wallet instance.

        Args:
            key: Wallet key to close (alternative to wallet param)

        Returns:
            True if closed, False if not found
        """
        wk = wallet or key
        if not wk or wk not in self.wallets:
            return False
        inst = self.wallets[wk]
        # Cancel event tasks
        for task in inst.event_tasks:
            task.cancel()
        # Close gRPC and stop LND
        try:
            await inst.grpc_client.close()
        except Exception:
            pass
        try:
            await inst.process.stop()
        except Exception:
            pass
        # Stop Tor process if running
        if inst.tor_process:
            try:
                await inst.tor_process.stop()
            except Exception:
                pass
        # Stop ElectrumX monitor if running
        if inst.electrumx_monitor:
            try:
                await inst.electrumx_monitor.stop()
            except Exception:
                pass
        del self.wallets[wk]
        if wk in self.wallets_updates:
            del self.wallets_updates[wk]
        # Update seed map on disk
        self._save_seed_map()
        logger.info(f"Wallet closed: {wk}")
        return True

    # -------------------------------------------------------------------------
    # RPC Methods - Transaction operations
    # -------------------------------------------------------------------------

    @rpc
    async def get_transaction(self, tx_hash, use_spv=False, wallet=None):
        """Get details for an on-chain transaction.

        Args:
            tx_hash: Transaction hash to look up
            use_spv: Ignored (LND handles verification internally)

        Returns:
            Dict with transaction details
        """
        if not wallet or wallet not in self.wallets:
            raise Exception("Wallet not loaded for transaction lookup")
        client = self._get_client(wallet)
        txs = await client.get_transactions()
        for tx in txs:
            if tx.tx_hash == tx_hash:
                return {
                    "txid": tx.tx_hash,
                    "amount": format_satoshis(tx.amount),
                    "num_confirmations": tx.num_confirmations,
                    "block_hash": tx.block_hash,
                    "block_height": tx.block_height,
                    "time_stamp": tx.time_stamp,
                    "total_fees": format_satoshis(tx.total_fees),
                    "confirmations": tx.num_confirmations,
                }
        raise Exception("No such mempool or blockchain transaction")

    @rpc
    def get_tx_size(self, raw_tx: dict, wallet=None) -> int:
        """Estimate transaction size from raw transaction data.

        Args:
            raw_tx: Raw transaction hex or dict

        Returns:
            Estimated size in virtual bytes
        """
        if isinstance(raw_tx, str):
            # Rough estimate: hex string length / 2 gives bytes
            # For segwit, vsize ~= bytes * 0.75 (approximate)
            return max(1, len(raw_tx) // 2)
        return 250  # default estimate for a typical 1-input-2-output tx

    @rpc
    def get_tx_hash(self, raw_tx: dict, wallet=None) -> str:
        """Compute transaction ID from raw transaction.

        Args:
            raw_tx: Raw transaction hex

        Returns:
            Transaction hash
        """
        # For LND, we typically don't have raw tx parsing in Python
        # Return a placeholder - callers should use the txid from LND responses
        raise Exception("get_tx_hash requires broadcasting; use LND's transaction API directly")

    @rpc
    async def get_default_fee(self, tx, wallet=None) -> str:
        """Estimate the default fee for a transaction.

        Args:
            tx: Transaction size in bytes, or raw tx string

        Returns:
            Fee in BTC (formatted)
        """
        # Use any available wallet's client, or raise
        client = self._get_any_client(wallet)
        sat_per_kw = await client.estimate_fee(conf_target=6)
        # Convert sat/kw to sat/vbyte: sat_per_kw / 250
        sat_per_vbyte = max(1, sat_per_kw // 250)
        size = self.get_tx_size(tx) if isinstance(tx, str | dict) else int(tx)
        fee_sat = sat_per_vbyte * size
        return format_satoshis(fee_sat)

    @rpc
    async def recommended_fee(self, target, wallet=None) -> float:
        """Get recommended fee rate for a confirmation target.

        Args:
            target: Number of blocks for confirmation target

        Returns:
            Fee rate in sat/vbyte
        """
        client = self._get_any_client(wallet)
        sat_per_kw = await client.estimate_fee(conf_target=int(target))
        return max(1, sat_per_kw // 250)  # sat/kw to sat/vbyte

    @rpc(requires_wallet=True, requires_network=True)
    async def get_used_fee(self, tx_hash, wallet):
        """Get the actual fee paid by a transaction.

        Args:
            tx_hash: Transaction hash

        Returns:
            Fee in BTC (formatted)
        """
        client = self._get_client(wallet)
        txs = await client.get_transactions()
        for tx in txs:
            if tx.tx_hash == tx_hash:
                return format_satoshis(abs(tx.total_fees))
        raise Exception("No such blockchain transaction")

    @rpc(requires_wallet=False, requires_network=False)
    async def validateaddress(self, address, wallet=None, **kwargs):
        """Validate a Bitcoin on-chain address.

        Bitcart's payout validator calls `coin.server.validateaddress(...)`
        before accepting a payout destination; without this method,
        PayoutService.validate raises ProcedureNotFoundError. We accept any
        well-formed bech32 (segwit/taproot) or base58 (P2PKH/P2SH) address
        for the currently-configured network; LND will reject malformed
        addresses at send time anyway.
        """
        if not isinstance(address, str) or not address:
            return False
        # LND_NETWORK is set in load_env() and is one of:
        #   mainnet, testnet3, testnet4, signet, regtest
        net = (getattr(self, "LND_NETWORK", "") or "").lower()
        hrps = {
            "mainnet":  ("bc",   (0x00, 0x05)),
            "testnet3": ("tb",   (0x6f, 0xc4)),
            "testnet4": ("tb",   (0x6f, 0xc4)),
            "signet":   ("tb",   (0x6f, 0xc4)),
            "regtest":  ("bcrt", (0x6f, 0xc4)),
        }
        hrp, base58_versions = hrps.get(net, hrps["mainnet"])
        addr = address.strip()
        # Bech32 / bech32m (segwit v0 + taproot). Structural check is fine
        # here: LND will reject malformed addresses at send time as a backstop.
        if addr.lower().startswith(hrp + "1"):
            import re
            return bool(re.fullmatch(rf"{hrp}1[02-9ac-hj-np-z]{{6,87}}", addr.lower()))
        # Legacy base58 (P2PKH/P2SH).
        try:
            import hashlib
            ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
            num = 0
            for c in addr:
                if c not in ALPHABET:
                    return False
                num = num * 58 + ALPHABET.index(c)
            decoded = num.to_bytes((num.bit_length() + 7) // 8, "big")
            # Account for leading "1" → leading zero bytes.
            pad = len(addr) - len(addr.lstrip("1"))
            decoded = b"\x00" * pad + decoded
            if len(decoded) != 25:
                return False
            payload, checksum = decoded[:21], decoded[21:]
            if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != checksum:
                return False
            return payload[0] in base58_versions
        except Exception:
            return False

    @rpc(requires_wallet=True, requires_network=True)
    async def payto(self, destination, amount, fee=None, wallet=None, **kwargs):
        """Send Bitcoin on-chain or pay a lightning invoice.

        If destination looks like a BOLT11 invoice, pays via lightning.
        Otherwise sends on-chain.

        Args:
            destination: Address or BOLT11 invoice
            amount: Amount in BTC (for on-chain) or satoshis
            fee: Optional fee rate in sat/vbyte

        Returns:
            Dict with transaction details
        """
        client = self._get_client(wallet)
        # Check if lightning invoice
        if destination.lower().startswith("ln"):
            response = await client.send_payment_sync(destination)
            if response.payment_error:
                raise Exception(response.payment_error)
            return {
                "txid": response.payment_hash.hex(),
                "payment_preimage": response.payment_preimage.hex(),
            }
        # On-chain payment
        amount_sat = int(Decimal(str(amount)) * Decimal("100000000"))
        sat_per_vbyte = int(fee) if fee else 0
        txid = await client.send_coins(
            addr=destination,
            amount=amount_sat,
            sat_per_vbyte=sat_per_vbyte,
        )
        # The payout flow calls coin.pay_to(broadcast=False), which translates
        # to server.payto(addtransaction=False). The Bitcart SDK also has an
        # `unsigned=True` convention. Either signal means "return raw_tx for
        # later broadcast" — but LND's SendCoins already broadcasts, so we
        # return the txid as a plain string and the subsequent broadcast()
        # call no-ops on the already-broadcast tx.
        if kwargs.get("unsigned") or kwargs.get("addtransaction") is False:
            return txid
        return {"txid": txid}

    @rpc(requires_wallet=True, requires_network=True)
    async def broadcast(self, tx, wallet):
        """Broadcast a raw transaction to the network.

        Args:
            tx: Raw transaction hex, OR a 64-char txid hex string returned by
                payto(unsigned=True) — in the latter case the tx is already on
                the network so this becomes a no-op.

        Returns:
            txid (string) on success.
        """
        # Already-broadcast path: payto(unsigned=True) returns a 32-byte txid
        # as 64 hex chars; broadcast then receives that same string.
        if isinstance(tx, str) and len(tx) == 64 and all(c in "0123456789abcdefABCDEF" for c in tx):
            return tx
        client = self._get_client(wallet)
        tx_bytes = bytes.fromhex(tx) if isinstance(tx, str) else tx
        error = await client.publish_transaction(tx_bytes)
        if error:
            raise Exception(error)
        return True

    @rpc(requires_wallet=True)
    async def addtransaction(self, tx, wallet=None, **kwargs):
        """Add a signed transaction to the wallet before broadcasting.

        In Electrum, this registers the tx in the local wallet DB before
        broadcast. LND handles signing and wallet state internally, so
        this is a no-op — the transaction is already known to LND after
        SendCoins or will be learned from the network after broadcast.

        Returns:
            True (always succeeds)
        """
        return True

    @rpc(requires_wallet=True, requires_network=True)
    async def paytomany(self, outputs, fee=None, feerate=None, addtransaction=True, wallet=None, **kwargs):
        """Send Bitcoin to multiple destinations.

        LND's SendCoins only supports single-destination sends, so this
        sends to each destination individually. When addtransaction=True
        (broadcast mode), sends are executed immediately. When False,
        only the first output is sent and the txid is returned in raw-tx
        format for compatibility with the payout manager flow.

        Args:
            outputs: List of [address, amount] pairs (amount in BTC)
            fee: Optional fixed fee
            feerate: Optional fee rate in sat/vbyte
            addtransaction: If True, broadcast immediately

        Returns:
            Txid string (if broadcast) or raw-tx-like dict (if not broadcast)
        """
        client = self._get_client(wallet)
        sat_per_vbyte = int(feerate or fee or 0)
        txids = []
        for destination, amount in outputs:
            amount_sat = int(Decimal(str(amount)) * Decimal("100000000"))
            txid = await client.send_coins(
                addr=destination,
                amount=amount_sat,
                sat_per_vbyte=sat_per_vbyte,
            )
            txids.append(txid)
        if not addtransaction:
            # Payout manager expects a raw tx string that it will later broadcast.
            # LND already broadcast, so return the txid as the "raw tx" — the
            # subsequent addtransaction() is a no-op and broadcast() will
            # recognize an already-broadcast tx.
            return txids[0] if txids else ""
        return txids[0] if len(txids) == 1 else txids

    @rpc(requires_wallet=True)
    async def history(self, wallet):
        """Get combined on-chain and lightning payment history.

        Returns:
            List of transaction/payment dicts sorted by timestamp
        """
        client = self._get_client(wallet)
        result = []
        # On-chain transactions
        txs = await client.get_transactions()
        for tx in txs:
            result.append({
                "type": "on-chain",
                "txid": tx.tx_hash,
                "amount": format_satoshis(tx.amount),
                "confirmations": tx.num_confirmations,
                "timestamp": tx.time_stamp,
                "fee": format_satoshis(tx.total_fees),
            })
        # Lightning payments (outgoing)
        payments = await client.list_payments()
        for payment in payments:
            result.append({
                "type": "lightning",
                "txid": payment.payment_hash,
                "amount": format_satoshis(-payment.value_sat),
                "fee": format_satoshis(payment.fee_sat),
                "timestamp": payment.creation_date,
                "status": payment.status,
            })
        # Lightning invoices (incoming)
        invoices = await client.list_invoices()
        for inv in invoices:
            if inv.state == INVOICE_SETTLED:
                result.append({
                    "type": "lightning-invoice",
                    "txid": inv.r_hash.hex(),
                    "amount": format_satoshis(inv.amt_paid_sat),
                    "timestamp": inv.settle_date,
                    "memo": inv.memo,
                })
        # Sort by timestamp descending
        result.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return result

    # -------------------------------------------------------------------------
    # RPC Methods - Invoice and request operations
    # -------------------------------------------------------------------------

    @rpc(requires_wallet=True, requires_network=True)
    async def add_request(self, amount=None, memo="", expiration=3600, expiry=None, force=False, wallet=None, **kwargs):
        """Create a new payment request with both on-chain and lightning options.

        Args:
            amount: Amount in BTC (can be Decimal or string)
            memo: Optional description
            expiration: Expiry in seconds (default 1 hour)
            expiry: Alternative name for expiration (used by SDK)
            force: Ignored (compatibility with Electrum SDK)

        Returns:
            Dict with payment request details including address and BOLT11 invoice
        """
        # SDK passes 'expiry' while our param is 'expiration'
        exp_seconds = int(expiry if expiry is not None else expiration)
        client = self._get_client(wallet)
        # Convert BTC to satoshis
        if amount is not None:
            amount_sat = int(Decimal(str(amount)) * Decimal("100000000"))
        else:
            amount_sat = 0
        # Create lightning invoice
        invoice_response = await client.add_invoice(
            value=amount_sat,
            memo=memo,
            expiry=exp_seconds,
        )
        # Also generate an on-chain address as fallback
        address = await client.new_address(addr_type=0)
        r_hash_hex = invoice_response.r_hash.hex()
        amount_str = str(amount) if amount is not None else "0"
        # Store r_hash → address mapping for on-chain payment tracking (persisted to SQLite)
        if wallet in self.wallets:
            async with self.wallets[wallet].request_lock:
                self.wallets[wallet].request_addresses[r_hash_hex] = {
                    "address": address,
                    "amount_sat": amount_sat,
                }
            self._save_request_address(wallet, r_hash_hex, address, amount_sat)
            # Subscribe to ElectrumX monitor for zero-conf detection
            if self.wallets[wallet].electrumx_monitor:
                await self.wallets[wallet].electrumx_monitor.watch_address(
                    address, r_hash_hex, amount_sat
                )
        return {
            "id": r_hash_hex,
            "request_id": r_hash_hex,
            "address": address,
            "lightning": invoice_response.payment_request,
            "lightning_invoice": invoice_response.payment_request,
            "amount": amount_str,
            "amount_BTC": amount_str,
            "amount_BTCLND": amount_str,
            "status": PR_UNPAID,
            "status_str": PR_STATUS_STR[PR_UNPAID],
            "URI": f"bitcoin:{address}?amount={amount_str}",
            "rhash": r_hash_hex,
        }

    @rpc(requires_wallet=True)
    async def get_request(self, key, wallet=None, **kwargs):
        """Get payment request details by payment hash.

        Checks both the LND invoice status (for lightning payments) AND
        the on-chain address balance (for on-chain payments). This allows
        Bitcart's worker to detect payments made via either method.

        Args:
            key: Payment hash (hex) of the invoice

        Returns:
            Dict with invoice details including status and amounts
        """
        client = self._get_client(wallet)
        r_hash = bytes.fromhex(key)
        invoice = await client.lookup_invoice(r_hash)
        status = self._invoice_state_to_pr_status(invoice.state)
        amount_str = format_satoshis(invoice.value)
        tx_hashes = []
        sent_amount = "0"
        # Check lightning payment status
        if status == PR_PAID:
            tx_hashes = [key]
            sent_amount = format_satoshis(invoice.amt_paid_sat)
        else:
            # Check on-chain address balance for this request
            onchain_info = self._get_request_address_info(wallet, key)
            if onchain_info:
                address = onchain_info["address"]
                received_sat, onchain_tx_hashes = await self._check_address_received(
                    client, address
                )
                if received_sat > 0:
                    sent_amount = format_satoshis(received_sat)
                    tx_hashes = onchain_tx_hashes if onchain_tx_hashes else [key]
                    if received_sat >= onchain_info.get("amount_sat", 0):
                        status = PR_PAID
                    else:
                        status = PR_UNCONFIRMED  # partial payment received
        # Also check on-chain transactions for tx hashes if we have an address
        onchain_info = self._get_request_address_info(wallet, key)
        address = onchain_info["address"] if onchain_info else key
        return {
            "id": key,
            "address": address,
            "amount": amount_str,
            "amount_BTC": amount_str,
            "amount_BTCLND": amount_str,
            "status": status,
            "status_str": PR_STATUS_STR.get(status, "Unknown"),
            "lightning": invoice.payment_request,
            "rhash": key,
            "memo": invoice.memo,
            "expiration": invoice.expiry,
            "creation_date": invoice.creation_date,
            "tx_hashes": tx_hashes,
            "sent_amount": sent_amount,
        }

    async def _check_address_received(self, client, address: str) -> tuple[int, list[str]]:
        """Check how much was received at an address using UTXOs and transaction history.

        ListUnspent is preferred (gives per-UTXO amounts) but may miss unconfirmed
        transactions in neutrino mode. GetTransactions with output_details is used
        as a fallback to detect unconfirmed payments.

        Returns:
            Tuple of (received_sats, list_of_tx_hashes)
        """
        received_sat = 0
        tx_hashes = []
        try:
            # Primary: check confirmed UTXOs
            utxos = await client.list_unspent()
            for utxo in utxos:
                if utxo.address == address:
                    received_sat += utxo.amount_sat
                    if hasattr(utxo, "outpoint") and utxo.outpoint:
                        txid = utxo.outpoint.txid_str
                        if txid and txid not in tx_hashes:
                            tx_hashes.append(txid)
        except Exception:
            logger.debug(f"ListUnspent failed for {address[:20]}")
        if received_sat > 0:
            return received_sat, tx_hashes
        # Fallback: check transaction history (catches unconfirmed in neutrino mode)
        try:
            txs = await client.get_transactions()
            for tx in txs:
                # Use output_details for per-output amounts
                for out in getattr(tx, "output_details", []):
                    if getattr(out, "address", "") == address and getattr(out, "is_our_address", False):
                        received_sat += out.amount
                        if tx.tx_hash and tx.tx_hash not in tx_hashes:
                            tx_hashes.append(tx.tx_hash)
        except Exception:
            logger.debug(f"GetTransactions fallback failed for {address[:20]}")
        return received_sat, tx_hashes

    def _get_request_address_info(self, wallet_key: str, r_hash: str) -> dict | None:
        """Look up the on-chain address associated with a payment request."""
        if wallet_key and wallet_key in self.wallets:
            return self.wallets[wallet_key].request_addresses.get(r_hash)
        return None

    @rpc(requires_wallet=True)
    async def get_invoice(self, key, wallet):
        """Get formatted invoice details (alias for get_request).

        Args:
            key: Payment hash (hex) of the invoice

        Returns:
            Dict with invoice details
        """
        return await self.get_request(key, wallet=wallet)

    @rpc(requires_wallet=True)
    async def list_requests(self, pending=False, expired=False, paid=False, wallet=None, **kwargs):
        """List payment requests filtered by status.

        Args:
            pending: Include pending requests
            expired: Include expired requests
            paid: Include paid requests

        Returns:
            List of invoice dicts
        """
        client = self._get_client(wallet)
        invoices = await client.list_invoices()
        result = []
        for inv in invoices:
            status = self._invoice_state_to_pr_status(inv.state)
            include = False
            if pending and status == PR_UNPAID:
                include = True
            if expired and status == PR_EXPIRED:
                include = True
            if paid and status == PR_PAID:
                include = True
            if not pending and not expired and not paid:
                include = True  # no filter, return all
            if include:
                result.append({
                    "id": inv.r_hash.hex(),
                    "amount": format_satoshis(inv.value),
                    "status": status,
                    "status_str": PR_STATUS_STR.get(status, "Unknown"),
                    "lightning": inv.payment_request,
                    "memo": inv.memo,
                })
        return result

    @rpc(requires_wallet=True)
    async def rmrequest(self, key, wallet):
        """Remove/cancel a payment request.

        Args:
            key: Payment hash (hex) of the invoice to cancel

        Returns:
            True on success
        """
        client = self._get_client(wallet)
        await client.cancel_invoice(bytes.fromhex(key))
        return True

    @rpc(requires_wallet=True)
    async def clear_requests(self, wallet):
        """Cancel all pending invoices.

        Returns:
            True on success
        """
        client = self._get_client(wallet)
        invoices = await client.list_invoices(pending_only=True)
        for inv in invoices:
            try:
                await client.cancel_invoice(inv.r_hash)
            except Exception:
                pass  # skip already settled/canceled
        return True

    def _invoice_state_to_pr_status(self, state: int) -> int:
        """Convert LND invoice state to Bitcart PR_* status code."""
        return {
            INVOICE_OPEN: PR_UNPAID,
            INVOICE_SETTLED: PR_PAID,
            INVOICE_CANCELED: PR_EXPIRED,
            INVOICE_ACCEPTED: PR_INFLIGHT,
        }.get(state, PR_UNKNOWN)

    # -------------------------------------------------------------------------
    # RPC Methods - Lightning channel operations
    # -------------------------------------------------------------------------

    @rpc(requires_wallet=True, requires_network=True)
    async def open_channel(self, node_id, amount, push_amount=0, private=False, wallet=None, **kwargs):
        """Open a lightning channel with a remote node.

        Accepts node_id in any of these formats:
            - pubkey (hex only)
            - pubkey@host
            - pubkey@host:port
            - pubkey@hostname.onion:port

        If a host address is included, automatically connects to the peer first.

        Args:
            node_id: Remote node's public key, optionally with @host:port
            amount: Channel capacity in satoshis
            push_amount: Amount to push to remote side
            private: If True, open an unannounced channel (not broadcast to network)

        Returns:
            Dict with channel point details
        """
        client = self._get_client(wallet)
        if isinstance(private, str):
            private = private.lower() in ("true", "1", "yes")
        # Parse pubkey@host:port if provided
        pubkey = node_id
        if "@" in node_id:
            pubkey, host = node_id.split("@", 1)
            # Auto-connect to peer before opening channel
            try:
                await client.connect_peer(pubkey, host)
            except Exception as e:
                err = str(e).lower()
                if "already connected" not in err:
                    # Connection failed — raise immediately with the actual error
                    # instead of letting OpenChannelSync give a less helpful "peer not online"
                    raise Exception(f"Could not connect to peer {pubkey[:16]}...@{host}: {e}")
            import asyncio
            await asyncio.sleep(1)
        channel_point = await client.open_channel_sync(
            node_pubkey=pubkey,
            local_funding_amount=int(amount),
            push_sat=int(push_amount),
            private=bool(private),
        )
        return {
            "channel_point": f"{channel_point.funding_txid_str}:{channel_point.output_index}",
            "funding_txid": channel_point.funding_txid_str,
            "output_index": channel_point.output_index,
        }

    @rpc(requires_wallet=True, requires_network=True)
    async def close_channel(self, channel_point, force=False, wallet=None):
        """Close a lightning channel.

        Args:
            channel_point: Channel point in "txid:index" format
            force: Force close (unilateral)

        Returns:
            True if close initiated
        """
        client = self._get_client(wallet)
        close_stream = await client.close_channel(channel_point, force=force)
        # Read the first update to confirm the close was initiated
        async for update in close_stream:
            return {"closing_txid": getattr(update, "closing_txid", "")}
        return True

    @rpc(requires_wallet=True)
    async def list_channels(self, wallet):
        """List all lightning channels including pending ones.

        Returns:
            List of channel detail dicts with state field indicating
            OPEN, DISCONNECTED, PENDING_OPEN, PENDING_CLOSE, or FORCE_CLOSING.
        """
        client = self._get_client(wallet)
        result = []
        # Get per-channel fee schedules
        fee_map = {}
        try:
            fee_reports = await client.fee_report()
            for fr in fee_reports:
                fee_map[fr.channel_point] = {
                    "base_fee_msat": fr.base_fee_msat,
                    "fee_rate_ppm": fr.fee_per_mil,
                }
        except Exception:
            pass
        # Active/inactive confirmed channels
        channels = await client.list_channels()
        for ch in channels:
            fees = fee_map.get(ch.channel_point, {})
            base_fee_sats = fees.get("base_fee_msat", 0) / 1000
            fee_rate_ppm = fees.get("fee_rate_ppm", 0)
            result.append({
                "channel_point": ch.channel_point,
                "channel_id": ch.channel_point,
                "remote_pubkey": ch.remote_pubkey,
                "capacity": ch.capacity,
                "local_balance": ch.local_balance,
                "remote_balance": ch.remote_balance,
                "active": ch.active,
                "private": ch.private,
                "state": "OPEN" if ch.active else "DISCONNECTED",
                "peer_state": "OPEN" if ch.active else "DISCONNECTED",
                "initiator": ch.initiator,
                "commit_fee": ch.commit_fee,
                "total_satoshis_sent": ch.total_satoshis_sent,
                "total_satoshis_received": ch.total_satoshis_received,
                "num_updates": ch.num_updates,
                "base_fee_sats": base_fee_sats,
                "fee_rate_ppm": fee_rate_ppm,
                "fee_rate_percent": f"{fee_rate_ppm / 10000:.4f}",
            })
        # Pending channels (not yet confirmed on-chain)
        try:
            pending = await client.pending_channels()
            for pch in pending.pending_open_channels:
                ch = pch.channel
                result.append({
                    "channel_point": ch.channel_point,
                    "channel_id": ch.channel_point,
                    "remote_pubkey": ch.remote_node_pub,
                    "capacity": ch.capacity,
                    "local_balance": ch.local_balance,
                    "remote_balance": ch.remote_balance,
                    "active": False,
                    "state": "PENDING_OPEN",
                    "peer_state": "PENDING_OPEN",
                    "initiator": ch.initiator == 1,
                    "commit_fee": pch.commit_fee,
                    "total_satoshis_sent": 0,
                    "total_satoshis_received": 0,
                    "num_updates": 0,
                })
            for pch in pending.pending_closing_channels:
                ch = pch.channel
                result.append({
                    "channel_point": ch.channel_point,
                    "channel_id": ch.channel_point,
                    "remote_pubkey": ch.remote_node_pub,
                    "capacity": ch.capacity,
                    "local_balance": ch.local_balance,
                    "remote_balance": ch.remote_balance,
                    "active": False,
                    "state": "PENDING_CLOSE",
                    "peer_state": "PENDING_CLOSE",
                    "initiator": ch.initiator == 1,
                    "commit_fee": 0,
                    "total_satoshis_sent": 0,
                    "total_satoshis_received": 0,
                    "num_updates": 0,
                })
            for pch in pending.pending_force_closing_channels:
                ch = pch.channel
                result.append({
                    "channel_point": ch.channel_point,
                    "channel_id": ch.channel_point,
                    "remote_pubkey": ch.remote_node_pub,
                    "capacity": ch.capacity,
                    "local_balance": ch.local_balance,
                    "remote_balance": ch.remote_balance,
                    "active": False,
                    "state": "FORCE_CLOSING",
                    "peer_state": "FORCE_CLOSING",
                    "initiator": ch.initiator == 1,
                    "commit_fee": 0,
                    "total_satoshis_sent": 0,
                    "total_satoshis_received": 0,
                    "num_updates": 0,
                })
        except Exception:
            pass  # pending channels RPC may not be available during startup
        return result

    @rpc(requires_wallet=True, requires_network=True)
    async def lnpay(self, invoice, wallet):
        """Pay a lightning invoice.

        Args:
            invoice: BOLT11 payment request

        Returns:
            Dict with payment details
        """
        client = self._get_client(wallet)
        response = await client.send_payment_sync(invoice)
        if response.payment_error:
            raise Exception(response.payment_error)
        return {
            "payment_hash": response.payment_hash.hex(),
            "payment_preimage": response.payment_preimage.hex(),
        }

    @rpc(requires_wallet=True)
    async def add_peer(self, connect_str, wallet):
        """Connect to a lightning network peer.

        Args:
            connect_str: Peer address in "pubkey@host:port" format

        Returns:
            True on success
        """
        if "@" not in connect_str:
            raise Exception("Invalid peer address format. Use: pubkey@host:port")
        pubkey, host = connect_str.split("@", 1)
        client = self._get_client(wallet)
        await client.connect_peer(pubkey, host)
        return True

    @rpc(requires_wallet=True)
    async def list_peers(self, wallet):
        """List connected lightning network peers.

        Returns:
            List of peer detail dicts
        """
        client = self._get_client(wallet)
        peers = await client.list_peers()
        return [
            {
                "pub_key": p.pub_key,
                "address": p.address,
                "bytes_sent": p.bytes_sent,
                "bytes_recv": p.bytes_recv,
                "sat_sent": p.sat_sent,
                "sat_recv": p.sat_recv,
                "inbound": p.inbound,
                "ping_time": p.ping_time,
            }
            for p in peers
        ]

    @rpc(requires_wallet=True)
    async def nodeid(self, wallet):
        """Get this node's public key (identity).

        Returns:
            Node public key hex string
        """
        if wallet in self.wallets and self.wallets[wallet].identity_pubkey:
            return self.wallets[wallet].identity_pubkey
        client = self._get_client(wallet)
        info = await client.get_info()
        return info.identity_pubkey

    @rpc(requires_wallet=True)
    async def get_inbound_capacity(self, wallet, amount_sat=0):
        """Check available inbound lightning capacity.

        Returns the total remote balance across all active channels,
        and whether it's sufficient for a given amount.

        Args:
            amount_sat: Amount in satoshis to check capacity for (0 = just return capacity)

        Returns:
            Dict with total_inbound_sats and has_capacity fields
        """
        client = self._get_client(wallet)
        channels = await client.list_channels(active_only=True)
        total_inbound = sum(ch.remote_balance for ch in channels)
        return {
            "total_inbound_sats": total_inbound,
            "has_capacity": total_inbound >= int(amount_sat) if amount_sat else total_inbound > 0,
            "active_channels": len(channels),
        }

    @rpc(requires_wallet=True)
    async def get_node_uri(self, wallet):
        """Get this node's full URI(s) including address and port.

        Returns URIs for both clearnet and Tor (if enabled).
        Format: pubkey@host:port

        Returns:
            Dict with clearnet_uri, onion_uri (if Tor), and all uris
        """
        client = self._get_client(wallet)
        info = await client.get_info()
        p2p_port = self.wallets[wallet].p2p_port
        uris = self._build_node_uris(
            info.identity_pubkey, p2p_port, list(info.uris) if info.uris else []
        )
        # Update cached URIs
        if wallet in self.wallets:
            self.wallets[wallet].uris = uris
        # Separate clearnet and onion URIs
        clearnet_uris = [u for u in uris if ".onion:" not in u]
        onion_uris = [u for u in uris if ".onion:" in u]
        return {
            "uris": uris,
            "clearnet_uri": clearnet_uris[0] if clearnet_uris else "",
            "onion_uri": onion_uris[0] if onion_uris else "",
            "identity_pubkey": info.identity_pubkey,
            "tor_enabled": wallet in self.wallets and self.wallets[wallet].tor_process is not None,
        }

    # -------------------------------------------------------------------------
    # RPC Methods - Payment URL operations
    # -------------------------------------------------------------------------

    @rpc
    async def modifypaymenturl(self, url, amount, divisibility=None, wallet=None):
        """Modify payment URL to include/change the amount.

        Handles both BIP21 URIs and BOLT11 invoices.

        Args:
            url: Payment URL (bitcoin: URI or BOLT11 invoice)
            amount: New amount in BTC

        Returns:
            Modified payment URL
        """
        # For BOLT11 invoices, we can't easily modify the amount without re-signing
        # Fall back to BIP21 URI modification
        return modify_payment_url("amount", url, amount)

    @rpc(requires_wallet=True)
    async def get_payment_uri(self, address, amount, wallet=None):
        """Build a BIP21 payment URI.

        Args:
            address: Bitcoin address
            amount: Amount in BTC

        Returns:
            BIP21 URI string
        """
        if not Decimal(str(amount)):
            return f"bitcoin:{address}"
        return f"bitcoin:{address}?amount={amount}"

    # -------------------------------------------------------------------------
    # RPC Methods - PSBT support (LND native)
    # -------------------------------------------------------------------------

    @rpc(requires_wallet=True, requires_network=True)
    async def finalizepsbt(self, psbt, wallet):
        """Finalize a PSBT and extract the final raw transaction.

        Args:
            psbt: Base64-encoded PSBT

        Returns:
            Hex-encoded raw transaction ready for broadcast
        """
        import base64

        client = self._get_client(wallet)
        psbt_bytes = base64.b64decode(psbt)
        _, raw_final_tx = await client.finalize_psbt(psbt_bytes)
        return raw_final_tx.hex()

    # -------------------------------------------------------------------------
    # RPC Methods - Stub/fallback methods (BTC-compatible interface)
    # -------------------------------------------------------------------------

    @rpc
    def validatecontract(self, address, wallet=None):
        """Validate smart contract address (always False for Bitcoin)."""
        return False

    @rpc
    def get_tokens(self, wallet=None):
        """Get token list (always empty for Bitcoin)."""
        return {}

    @rpc
    def getabi(self, wallet=None):
        """Get contract ABI (always empty for Bitcoin)."""
        return []

    @rpc
    def normalizeaddress(self, address, wallet=None):
        """Normalize a Bitcoin address (pass-through)."""
        return address

    @rpc(requires_wallet=True)
    def setrequestaddress(self, key, address, wallet):
        """Set custom address for payment request (not supported)."""
        return False

    @rpc
    async def switch_server(self, server, wallet=None):
        """Switch electrum server (not applicable for LND neutrino mode)."""
        return False

    @rpc(requires_wallet=True)
    async def adjustforhwsign(self, tx, fingerprint, derivation, wallet):
        """Prepare transaction for hardware wallet signing (not supported in LND)."""
        raise Exception("Hardware wallet signing is not supported with LND")

    @rpc
    async def getfingerprint(self, xpub, wallet=None):
        """Extract root fingerprint from xpub (not applicable for LND)."""
        raise Exception("getfingerprint is not supported with LND")

    @rpc
    async def is_synchronized(self, wallet=None):
        """Check if the daemon is synchronized with the network.

        Returns:
            True if synced
        """
        return not self.is_still_syncing(wallet)

    @rpc
    def list_wallets(self, wallet=None):
        """List all loaded wallets.

        Returns:
            List of wallet key strings
        """
        return list(self.wallets.keys())

    @rpc(requires_wallet=True)
    def get_logs(self, source="all", wallet=None):
        """Get recent log entries for this wallet's LND and Tor processes.

        Args:
            source: Filter by source - "lnd", "tor", or "all"

        Returns:
            List of log entry dicts with text, level, and source fields
        """
        if wallet not in self.wallets:
            return []
        inst = self.wallets[wallet]
        logs = []
        if source in ("all", "lnd"):
            logs.extend(list(inst.process.log_buffer))
        if source in ("all", "tor") and inst.tor_process:
            logs.extend(list(inst.tor_process.log_buffer))
        return logs

    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------

    def _get_any_client(self, wallet_key: str | None = None) -> LNDGrpcClient:
        """Get a gRPC client from the specified wallet or any available wallet.

        Used for methods that don't require a specific wallet (e.g., fee estimation).
        """
        if wallet_key and wallet_key in self.wallets:
            return self.wallets[wallet_key].grpc_client
        if self.wallets:
            return next(iter(self.wallets.values())).grpc_client
        raise Exception("No wallets loaded. Load a wallet first.")

    def _build_node_uris(self, pubkey: str, p2p_port: int, lnd_uris: list[str]) -> list[str]:
        """Build a complete list of node URIs from all known sources.

        Combines:
        - LND's self-reported URIs (may include onion and/or clearnet)
        - Machine's detected public IP
        - Configured hostname (from BITCART_HOST or BTCLND_EXTERNAL_IP)

        Args:
            pubkey: Node's identity public key
            p2p_port: The P2P listening port for this wallet's LND instance
            lnd_uris: URIs reported by LND's GetInfo

        Returns:
            Deduplicated list of pubkey@address:port URIs
        """
        uris = set(lnd_uris)
        if not pubkey:
            return list(uris)
        # Add hostname from EXTERNAL_IP / BITCART_HOST config
        if self.EXTERNAL_IP:
            hostname_uri = f"{pubkey}@{self.EXTERNAL_IP}:{p2p_port}"
            uris.add(hostname_uri)
        # Try to detect the machine's public IP
        local_ip = self._get_public_ip()
        if local_ip and local_ip != self.EXTERNAL_IP:
            ip_uri = f"{pubkey}@{local_ip}:{p2p_port}"
            uris.add(ip_uri)
        # Sort: clearnet first, then onion
        sorted_uris = sorted(uris, key=lambda u: (1 if ".onion:" in u else 0, u))
        return sorted_uris

    def _get_public_ip(self) -> str:
        """Attempt to detect the machine's public/external IP address.

        Tries multiple methods:
        1. Connect to an external host and check the socket's local address
        2. Fall back to empty string if detection fails

        Returns:
            IP address string, or empty string if undetectable
        """
        if hasattr(self, "_cached_public_ip"):
            return self._cached_public_ip
        import socket

        try:
            # This doesn't actually send data — just determines which interface
            # would be used to reach an external address
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                # Don't return private/loopback addresses as "public"
                if ip.startswith("127.") or ip.startswith("0."):
                    ip = ""
                self._cached_public_ip = ip
                return ip
        except Exception:
            self._cached_public_ip = ""
            return ""


if __name__ == "__main__":
    daemon = BTCLNDDaemon()
    daemon.start()
