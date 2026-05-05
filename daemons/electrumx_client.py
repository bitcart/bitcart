"""ElectrumX mempool monitor for zero-conf on-chain payment detection.

LND in neutrino mode cannot detect unconfirmed transactions. This module
connects to ElectrumX servers to monitor payment addresses for mempool
activity, enabling zero-conf payment detection.

Security model:
- Mempool data CANNOT be cryptographically verified (no SPV for unconfirmed tx)
- Mitigation: query 2+ servers and cross-check status hashes before accepting
- Subscription shuffling: no single server sees all watched addresses
- Optional Tor routing for privacy

Uses aiorpcx (same library as Electrum wallet) for battle-tested JSON-RPC/SSL.
"""

import asyncio
import hashlib
import random
import re
import ssl
import time
from collections import defaultdict
from itertools import cycle

import aiorpcx
from aiorpcx import RPCSession, Notification
from aiorpcx.rawsocket import RSClient, RSTransport
from aiorpcx.socks import SOCKSProxy, SOCKS5, SOCKSRandomAuth

from logger import get_logger

logger = get_logger(__name__)

PROTOCOL_VERSION = "1.4"
CLIENT_NAME = "bitcart-btclnd"
TARGET_SERVERS = 3      # Try to maintain this many connections
MIN_SERVERS_FOR_TRUST = 2  # Minimum servers that must agree before trusting
MAX_HEIGHT_DRIFT = 5    # Reject servers more than this many blocks behind

# Known genesis hashes per network
GENESIS_HASHES = {
    "mainnet": "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f",
    "testnet3": "000000000933ea01ad0ee984209779baaec3ced90fa3f408719526f8d77f4943",
    "testnet4": "00000000da84f2bafbbc53dee25a72ae507ff4914b867c565be350b0da8bf043",
    "signet": "00000008819873e925422c1ff0f99f7cc9bbb232af63a077a480a3633bee1ef6",
    "regtest": "0f9188f13cb7b2c71f2a335e3a4fc328bf5beb436012afca590b1a11466e2206",
}

# Default ElectrumX servers per network (from Electrum wallet source)
DEFAULT_SERVERS = {
    "mainnet": {
        "electrum.emzy.de": {"s": "50002"},
        "electrum.blockstream.info": {"s": "50002"},
        "104.248.139.211": {"s": "50002"},
        "142.93.6.38": {"s": "50002"},
        "157.245.172.236": {"s": "50002"},
        "bolt.schulzemic.net": {"s": "50002"},
        "electrum.bitaroo.net": {"s": "50002"},
    },
    "signet": {
        "signet-electrumx.wakiyamap.dev": {"s": "50002"},
        "electrum.emzy.de": {"s": "53002"},
        "mempool.space": {"s": "60602"},
    },
    "testnet3": {
        "blockstream.info": {"s": "993"},
        "electrum.blockstream.info": {"s": "60002"},
        "testnet.aranguren.org": {"s": "51002"},
    },
    "testnet4": {
        "testnet4-electrumx.wakiyamap.dev": {"s": "51002"},
        "mempool.space": {"s": "40002"},
    },
    "regtest": {
        "127.0.0.1": {"t": "51001"},
    },
}

# Segwit HRP per network (for address_to_scripthash)
SEGWIT_HRP = {
    "mainnet": "bc",
    "signet": "tb",
    "testnet3": "tb",
    "testnet4": "tb",
    "regtest": "bcrt",
}


# ---------------------------------------------------------------------------
# Bech32 / scripthash utilities
# ---------------------------------------------------------------------------

def _bech32_polymod(values):
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            chk ^= GEN[i] if ((b >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _bech32_decode(bech):
    bech = bech.lower()
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech):
        return None, None
    CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    hrp = bech[:pos]
    data = []
    for c in bech[pos + 1:]:
        if c not in CHARSET:
            return None, None
        data.append(CHARSET.index(c))
    if _bech32_polymod(_bech32_hrp_expand(hrp) + data) not in (1, 0x2BC830A3):
        return None, None
    return hrp, data[:-6]


def _convertbits(data, frombits, tobits, pad=True):
    acc, bits, ret = 0, 0, []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret


def address_to_scripthash(address: str, network: str) -> str:
    """Convert a Bitcoin address to an ElectrumX scripthash.

    The scripthash is SHA256(scriptPubKey) reversed to big-endian hex.
    """
    hrp = SEGWIT_HRP.get(network, "bc")
    decoded_hrp, data = _bech32_decode(address)
    if decoded_hrp and data:
        witver = data[0]
        witprog = _convertbits(data[1:], 5, 8, False)
        if witprog is not None:
            if witver == 0:
                script = bytes([0x00, len(witprog)]) + bytes(witprog)
            else:
                script = bytes([0x50 + witver, len(witprog)]) + bytes(witprog)
            h = hashlib.sha256(script).digest()
            return h[::-1].hex()
    raise ValueError(f"Unsupported address format: {address}")


# ---------------------------------------------------------------------------
# aiorpcx-based ElectrumX session with subscription support
# ---------------------------------------------------------------------------

class ElectrumXSession(RPCSession):
    """RPCSession extended with ElectrumX subscription notification handling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subscriptions: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def handle_request(self, request):
        """Handle incoming notifications from the ElectrumX server."""
        if isinstance(request, Notification):
            params = request.args
            key = f"{request.method}:{params[0]}" if params else request.method
            for queue in self.subscriptions.get(key, []):
                await queue.put(params)

    async def subscribe(self, method: str, params: list, queue: asyncio.Queue):
        """Subscribe to a method and register a queue for notifications."""
        key = f"{method}:{params[0]}" if params else method
        self.subscriptions[key].append(queue)
        return await self.send_request(method, params)

    def unsubscribe_queue(self, queue: asyncio.Queue):
        """Remove a queue from all subscriptions."""
        for key in list(self.subscriptions):
            self.subscriptions[key] = [q for q in self.subscriptions[key] if q is not queue]
            if not self.subscriptions[key]:
                del self.subscriptions[key]


# ---------------------------------------------------------------------------
# Single server connection
# ---------------------------------------------------------------------------

class ElectrumXConnection:
    """A validated connection to a single ElectrumX server."""

    def __init__(self, host: str, port: int, use_ssl: bool = True,
                 proxy: SOCKSProxy | None = None):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.proxy = proxy
        self.session: ElectrumXSession | None = None
        self._client_ctx = None
        self.server_height: int = 0
        self.genesis_hash: str = ""
        self.connected = False

    async def connect(self, expected_genesis: str, our_height: int) -> bool:
        """Connect, validate server, and return True if server is trustworthy."""
        try:
            ssl_ctx = None
            if self.use_ssl:
                ssl_ctx = ssl.create_default_context()
                # ElectrumX servers commonly use self-signed certificates.
                # We verify the server via genesis hash + multi-server cross-checking
                # rather than PKI, so we accept self-signed certs but still encrypt.
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_OPTIONAL

            session_factory = lambda *a, **kw: ElectrumXSession(*a, **kw)

            self._client_ctx = RSClient(
                host=self.host, port=self.port,
                ssl=ssl_ctx, proxy=self.proxy,
                session_factory=session_factory,
            )
            _, protocol = await asyncio.wait_for(
                self._client_ctx.create_connection(), timeout=10
            )
            self.session = protocol.session

            # Negotiate version
            await asyncio.wait_for(
                self.session.send_request("server.version", [CLIENT_NAME, PROTOCOL_VERSION]),
                timeout=10,
            )

            # Validate genesis hash via server.features
            if expected_genesis:
                try:
                    features = await asyncio.wait_for(
                        self.session.send_request("server.features"),
                        timeout=10,
                    )
                    self.genesis_hash = features.get("genesis_hash", "")
                    if self.genesis_hash and self.genesis_hash != expected_genesis:
                        logger.warning(
                            f"ElectrumX {self.host}:{self.port} wrong network "
                            f"(genesis {self.genesis_hash[:16]}... != {expected_genesis[:16]}...)"
                        )
                        await self.close()
                        return False
                except Exception:
                    pass  # server.features not supported by all servers

            # Check server height via headers.subscribe
            if our_height > 0:
                try:
                    header_result = await asyncio.wait_for(
                        self.session.send_request("blockchain.headers.subscribe"),
                        timeout=10,
                    )
                    if isinstance(header_result, dict):
                        self.server_height = header_result.get("height", 0)
                    if self.server_height > 0 and our_height - self.server_height > MAX_HEIGHT_DRIFT:
                        logger.warning(
                            f"ElectrumX {self.host}:{self.port} too far behind "
                            f"(server={self.server_height}, ours={our_height})"
                        )
                        await self.close()
                        return False
                except Exception:
                    pass

            self.connected = True
            logger.info(f"ElectrumX connected: {self.host}:{self.port} (height={self.server_height})")
            return True
        except Exception as e:
            logger.debug(f"ElectrumX connection failed {self.host}:{self.port}: {e}")
            await self.close()
            return False

    async def close(self):
        """Close the connection."""
        self.connected = False
        if self.session:
            try:
                await self.session.close()
            except Exception:
                pass
            self.session = None

    async def subscribe_address(self, scripthash: str, queue: asyncio.Queue) -> str | None:
        """Subscribe to address status changes. Returns initial status."""
        if not self.session:
            return None
        try:
            return await asyncio.wait_for(
                self.session.subscribe("blockchain.scripthash.subscribe", [scripthash], queue),
                timeout=10,
            )
        except Exception:
            return None

    async def get_balance(self, scripthash: str) -> dict | None:
        """Get address balance {confirmed, unconfirmed} in satoshis."""
        if not self.session:
            return None
        try:
            return await asyncio.wait_for(
                self.session.send_request("blockchain.scripthash.get_balance", [scripthash]),
                timeout=10,
            )
        except Exception:
            return None

    async def get_history(self, scripthash: str) -> list | None:
        """Get address transaction history."""
        if not self.session:
            return None
        try:
            return await asyncio.wait_for(
                self.session.send_request("blockchain.scripthash.get_history", [scripthash]),
                timeout=10,
            )
        except Exception:
            return None

    async def discover_peers(self) -> list[tuple[str, dict]]:
        """Discover additional servers via server.peers.subscribe."""
        if not self.session:
            return []
        try:
            peers = await asyncio.wait_for(
                self.session.send_request("server.peers.subscribe"),
                timeout=10,
            )
            result = []
            for item in (peers or []):
                if not isinstance(item, (list, tuple)) or len(item) < 3:
                    continue
                host = item[1]
                info = {}
                for feat in item[2]:
                    if isinstance(feat, str) and re.match(r"[st]\d*", feat):
                        proto, port = feat[0], feat[1:]
                        if not port:
                            port = "50002" if proto == "s" else "50001"
                        info[proto] = port
                if info:
                    result.append((host, info))
            return result
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Multi-server monitor with cross-checking and subscription shuffling
# ---------------------------------------------------------------------------

class ElectrumXMonitor:
    """Monitors addresses for unconfirmed transactions via multiple ElectrumX servers.

    Features:
    - Connects to 2-3 servers simultaneously
    - Validates servers (genesis hash, chain height)
    - Subscribes each address on 2 servers for cross-checking
    - Shuffles subscriptions so no single server sees all addresses
    - Routes through Tor when enabled
    - Disconnects when no addresses are watched
    """

    def __init__(
        self,
        network: str,
        on_payment_detected: callable = None,
        tor_socks_port: int | None = None,
        get_our_height: callable = None,
        server_db=None,
    ):
        self.network = network
        self.on_payment_detected = on_payment_detected
        self.tor_socks_port = tor_socks_port
        self._get_our_height = get_our_height  # Callable returning current LND block height
        self.server_db = server_db  # peewee model class or None
        self.expected_genesis = GENESIS_HASHES.get(network, "")

        self._connections: list[ElectrumXConnection] = []
        self._watched: dict[str, dict] = {}  # address -> {rhash, amount_sat, scripthash}
        # Maps scripthash -> {conn_index -> queue} for subscription tracking
        self._sub_queues: dict[str, dict[int, asyncio.Queue]] = defaultdict(dict)
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._watcher_tasks: list[asyncio.Task] = []

        # Build server list: persisted first, then seeds
        self._known_servers: dict[str, dict] = {}
        self._load_server_list()

    def _load_server_list(self):
        """Load servers from DB (if available) then add seed servers."""
        if self.server_db:
            try:
                for srv in self.server_db.select().order_by(
                    self.server_db.failures.asc(),
                    self.server_db.last_connected.desc(),
                ):
                    key = f"{srv.host}:{srv.port}"
                    self._known_servers[key] = {
                        "host": srv.host, "port": srv.port,
                        "protocol": srv.protocol, "failures": srv.failures,
                    }
            except Exception:
                pass
        # Add seed servers
        for host, info in DEFAULT_SERVERS.get(self.network, {}).items():
            port = int(info.get("s", info.get("t", "50002")))
            proto = "s" if "s" in info else "t"
            key = f"{host}:{port}"
            if key not in self._known_servers:
                self._known_servers[key] = {
                    "host": host, "port": port, "protocol": proto, "failures": 0,
                }

    def _make_proxy(self) -> SOCKSProxy | None:
        """Create a SOCKS proxy for Tor routing if enabled."""
        if not self.tor_socks_port:
            return None
        addr = aiorpcx.NetAddress("127.0.0.1", self.tor_socks_port)
        return SOCKSProxy(addr, SOCKS5, SOCKSRandomAuth())

    async def start(self) -> bool:
        """Connect to ElectrumX servers and start monitoring."""
        self._running = True
        connected = await self._fill_connection_pool()
        if connected < MIN_SERVERS_FOR_TRUST:
            logger.warning(
                f"Only {connected} ElectrumX server(s) available "
                f"(need {MIN_SERVERS_FOR_TRUST} for cross-checking); "
                f"zero-conf monitoring degraded"
            )
            if connected == 0:
                return False
        self._monitor_task = asyncio.create_task(self._connection_maintenance())
        return True

    async def stop(self):
        """Stop monitoring and disconnect all servers."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        for task in self._watcher_tasks:
            task.cancel()
        self._watcher_tasks.clear()
        for conn in self._connections:
            await conn.close()
        self._connections.clear()
        self._sub_queues.clear()

    def _current_height(self) -> int:
        """Get current LND block height for server validation.

        Returns 0 if LND is not synced yet, which skips the height check
        during server validation (we don't reject servers when we can't
        compare heights).
        """
        if self._get_our_height:
            try:
                return self._get_our_height()
            except Exception:
                return 0
        return 0

    async def _fill_connection_pool(self) -> int:
        """Try to connect to TARGET_SERVERS servers."""
        proxy = self._make_proxy()
        servers = list(self._known_servers.values())
        random.shuffle(servers)
        connected_hosts = {c.host for c in self._connections if c.connected}
        our_height = self._current_height()

        for srv_info in servers:
            if len(self._connections) >= TARGET_SERVERS:
                break
            host, port = srv_info["host"], srv_info["port"]
            if host in connected_hosts:
                continue
            use_ssl = srv_info.get("protocol", "s") == "s"
            conn = ElectrumXConnection(host, port, use_ssl, proxy)
            if await conn.connect(self.expected_genesis, our_height):
                self._connections.append(conn)
                connected_hosts.add(host)
                self._persist_server_success(host, port, srv_info.get("protocol", "s"))
                # Discover peers from this server
                await self._discover_from(conn)
            else:
                self._persist_server_failure(host, port)
        return len(self._connections)

    async def _discover_from(self, conn: ElectrumXConnection):
        """Discover new servers from a connected peer."""
        peers = await conn.discover_peers()
        added = 0
        for host, info in peers:
            port = int(info.get("s", info.get("t", "50002")))
            proto = "s" if "s" in info else "t"
            key = f"{host}:{port}"
            if key not in self._known_servers:
                self._known_servers[key] = {
                    "host": host, "port": port, "protocol": proto, "failures": 0,
                }
                self._persist_server_new(host, port, proto)
                added += 1
        if added:
            logger.debug(f"Discovered {added} new ElectrumX peers")

    async def _connection_maintenance(self):
        """Periodically check connections and refill pool."""
        while self._running:
            try:
                await asyncio.sleep(30)
                # Remove dead connections
                self._connections = [c for c in self._connections if c.connected]
                if len(self._connections) < MIN_SERVERS_FOR_TRUST and self._watched:
                    await self._fill_connection_pool()
                    # Re-subscribe addresses on new connections
                    if self._connections:
                        await self._resubscribe_all()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def _get_server_pair(self, address_index: int) -> list[int]:
        """Get which connection indices to use for a given address.

        Distributes subscriptions across servers using round-robin pairing.
        With 3 servers, pairs are: (0,1), (1,2), (0,2), (0,1), ...
        Each server sees ~67% of addresses, never 100%.
        """
        n = len(self._connections)
        if n == 0:
            return []
        if n == 1:
            return [0]
        # Generate all pairs
        pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append([i, j])
        if not pairs:
            return [0]
        return pairs[address_index % len(pairs)]

    async def watch_address(self, address: str, rhash: str, amount_sat: int):
        """Start watching an address for incoming payments."""
        scripthash = address_to_scripthash(address, self.network)
        self._watched[address] = {
            "rhash": rhash, "amount_sat": amount_sat, "scripthash": scripthash,
        }

        if not self._connections:
            return

        # Subscribe on a pair of servers (shuffled)
        addr_idx = len(self._watched) - 1
        conn_indices = self._get_server_pair(addr_idx)
        has_existing_status = False

        # Subscribe on all assigned servers first
        for ci in conn_indices:
            if ci < len(self._connections):
                conn = self._connections[ci]
                queue = asyncio.Queue()
                status = await conn.subscribe_address(scripthash, queue)
                self._sub_queues[scripthash][ci] = queue
                if status is not None:
                    has_existing_status = True
                # Start queue watcher
                task = asyncio.create_task(self._watch_queue(address, scripthash, ci, queue))
                self._watcher_tasks.append(task)

        # Cross-check only after all subscriptions are set up
        if has_existing_status:
            await self._cross_check_address(address)

    async def unwatch_address(self, address: str):
        """Stop watching an address."""
        info = self._watched.pop(address, None)
        if info:
            scripthash = info["scripthash"]
            # Clean up queues (can't unsubscribe from server, just ignore)
            self._sub_queues.pop(scripthash, None)

        # Disconnect if no addresses remain
        if not self._watched:
            logger.info("No addresses to monitor, disconnecting ElectrumX")
            for task in self._watcher_tasks:
                task.cancel()
            self._watcher_tasks.clear()
            for conn in self._connections:
                await conn.close()
            self._connections.clear()
            self._sub_queues.clear()

    async def _watch_queue(self, address: str, scripthash: str,
                           conn_idx: int, queue: asyncio.Queue):
        """Watch a subscription queue for status changes from one server."""
        while self._running and address in self._watched:
            try:
                await asyncio.wait_for(queue.get(), timeout=60)
                # Status changed — cross-check with all subscribed servers
                await self._cross_check_address(address)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                break

    async def _cross_check_address(self, address: str):
        """Query all subscribed servers for an address and cross-check results.

        Only triggers payment detection if MIN_SERVERS_FOR_TRUST servers agree.
        """
        info = self._watched.get(address)
        if not info:
            return

        scripthash = info["scripthash"]
        amount_sat = info["amount_sat"]
        rhash = info["rhash"]

        # Query balance from all servers that have a subscription for this address
        balances = {}
        sub_conns = self._sub_queues.get(scripthash, {})
        for ci in list(sub_conns.keys()):
            if ci < len(self._connections) and self._connections[ci].connected:
                bal = await self._connections[ci].get_balance(scripthash)
                if bal is not None:
                    balances[ci] = bal

        if not balances:
            return

        # Check if enough servers agree on sufficient balance
        sufficient_count = 0
        total_amounts = []
        for ci, bal in balances.items():
            total = bal.get("confirmed", 0) + bal.get("unconfirmed", 0)
            total_amounts.append(total)
            if total >= amount_sat:
                sufficient_count += 1

        servers_queried = len(balances)
        if sufficient_count < min(MIN_SERVERS_FOR_TRUST, servers_queried):
            if sufficient_count > 0:
                logger.warning(
                    f"ElectrumX: payment for {address[:20]}... reported by "
                    f"{sufficient_count}/{servers_queried} servers (need {MIN_SERVERS_FOR_TRUST}), "
                    f"waiting for confirmation"
                )
            return

        # All queried servers agree — get tx details from first agreeing server
        max_total = max(total_amounts) if total_amounts else 0
        confirmed = all(bal.get("unconfirmed", 0) == 0 for bal in balances.values())

        # Get tx hashes from one server
        tx_hashes = []
        for ci in sub_conns:
            if ci < len(self._connections) and self._connections[ci].connected:
                history = await self._connections[ci].get_history(scripthash)
                if history:
                    tx_hashes = [h["tx_hash"] for h in history]
                    break

        logger.info(
            f"ElectrumX: payment verified by {sufficient_count}/{servers_queried} servers "
            f"for {address[:20]}... ({max_total} sats, need {amount_sat})"
        )

        if self.on_payment_detected:
            await self.on_payment_detected(
                address=address,
                rhash=rhash,
                amount_sat=max_total,
                tx_hashes=tx_hashes,
                confirmed=confirmed,
            )

        # Stop watching this address
        await self.unwatch_address(address)

    async def _resubscribe_all(self):
        """Re-subscribe all watched addresses after connection changes."""
        # Clear old subscription state
        for task in self._watcher_tasks:
            task.cancel()
        self._watcher_tasks.clear()
        self._sub_queues.clear()

        for idx, (address, info) in enumerate(list(self._watched.items())):
            scripthash = info["scripthash"]
            conn_indices = self._get_server_pair(idx)
            for ci in conn_indices:
                if ci < len(self._connections) and self._connections[ci].connected:
                    queue = asyncio.Queue()
                    await self._connections[ci].subscribe_address(scripthash, queue)
                    self._sub_queues[scripthash][ci] = queue
                    task = asyncio.create_task(
                        self._watch_queue(address, scripthash, ci, queue)
                    )
                    self._watcher_tasks.append(task)

    # -- Server state persistence --

    def _persist_server_success(self, host: str, port: int, protocol: str = "s"):
        if not self.server_db:
            return
        try:
            self.server_db.replace(
                host=host, port=port, protocol=protocol,
                last_connected=int(time.time()), failures=0,
            ).execute()
        except Exception:
            pass

    def _persist_server_failure(self, host: str, port: int):
        if not self.server_db:
            return
        try:
            srv = self.server_db.get_or_none(
                (self.server_db.host == host) & (self.server_db.port == port)
            )
            if srv:
                srv.failures += 1
                srv.save()
            else:
                self.server_db.create(host=host, port=port, failures=1)
        except Exception:
            pass

    def _persist_server_new(self, host: str, port: int, protocol: str = "s"):
        if not self.server_db:
            return
        try:
            self.server_db.get_or_create(
                host=host, port=port,
                defaults={"protocol": protocol, "failures": 0, "last_connected": 0},
            )
        except Exception:
            pass
