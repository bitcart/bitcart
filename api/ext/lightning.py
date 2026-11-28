import asyncio
import re
import socket

from bitcart import BTC  # type: ignore[attr-defined]
from outbound_guard import OutboundGuard

DEFAULT_PORT = 9735
OWNER_DENIAL_HINT = ". Server admins can allow it in the wallet owner's allowed internal hosts"
RESOLVE_TIMEOUT = 15
CONNECTION_STRING = re.compile(
    r"(?P<node_id>[0-9a-f]{66})"
    r"(?:@(?:\[(?P<ipv6>[0-9a-f:.]+)\]|(?P<host>[a-z0-9._-]+))(?::(?P<port>[0-9]{1,5}))?)?"
)
ONION_HOST = re.compile(r"[a-z2-7]{56}\.onion")


class PeerDenied(Exception):
    pass


async def uses_gossip(coin: BTC) -> bool:
    return await coin.server.getconfig("use_gossip") is not False


async def resolve_peer(outbound: OutboundGuard, host: str, port: int) -> str:
    if not 0 < port < 65536:
        raise PeerDenied(f"Invalid port {port}")
    try:
        async with asyncio.timeout(RESOLVE_TIMEOUT):
            addr_infos = await outbound.resolve(host, port)
    except (OSError, ValueError) as e:
        raise PeerDenied(str(e)) from e
    ipv4 = [addr_info for addr_info in addr_infos if addr_info[0] == socket.AF_INET]
    return str((ipv4 or addr_infos)[0][4][0])


async def get_checked_connection_string(outbound: OutboundGuard, coin: BTC, connection_string: str) -> str:
    match = CONNECTION_STRING.fullmatch(connection_string.lower())
    if match is None:
        raise PeerDenied("Invalid connection string")
    node_id, host = match["node_id"], match["ipv6"] or match["host"]
    if host is None:
        if await uses_gossip(coin):
            raise PeerDenied("The address of the node is announced by the node itself")
        return node_id
    port = int(match["port"] or DEFAULT_PORT)
    if match["ipv6"] and ":" not in host:
        raise PeerDenied("Invalid IPv6 address")
    if not ONION_HOST.fullmatch(host):
        host = await resolve_peer(outbound, host, port)
    return f"{node_id}@[{host}]:{port}" if ":" in host else f"{node_id}@{host}:{port}"
