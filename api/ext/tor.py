import ipaddress
import json
import os
from dataclasses import asdict as dataclass_asdict
from dataclasses import dataclass
from typing import Optional

from api.logger import get_logger

from .. import settings, utils

logger = get_logger(__name__)

REDIS_KEY = "bitcartcc_tor_ext"


@dataclass(frozen=True)
class PortDefinition:
    virtual_port: int
    ip: str
    port: int


@dataclass
class HiddenService:
    name: str
    directory: str
    hostname: str
    port_definition: Optional[PortDefinition] = None


def is_onion(host):
    return host.lower().endswith(".onion")


def parse_hidden_service(line):
    if not line.startswith("HiddenServiceDir "):
        return
    parts = line.split()
    if len(parts) != 2:
        return
    return parts[1].strip()


def parse_hidden_service_port(line):
    if not line.startswith("HiddenServicePort "):
        return
    parts = line.split()
    if len(parts) != 3:
        return
    try:
        virtual_port = int(parts[1].strip())
        address_port = parts[2].strip().split(":")
        if len(address_port) != 2:
            return
        port = int(address_port[1])
        ip_address = str(ipaddress.ip_address(address_port[0].strip()))
        return PortDefinition(virtual_port, ip_address, port)
    except ValueError:
        return  # all parsing exceptions are ValueError


def get_hostname(service_dir):
    path = os.path.join(service_dir, "hostname")
    try:
        with open(path) as f:
            return f"http://{f.readline().strip()}"
    except OSError:
        return


def get_service_name(service_dir):
    return os.path.basename(service_dir).replace("-", " ")


def parse_torrc(torrc):
    if not torrc:
        return []
    try:
        with open(torrc) as f:
            lines = f.readlines()
    except OSError:
        return []
    services = []
    for line in lines:
        line = line.strip()
        hidden_service = parse_hidden_service(line)
        hidden_service_port = parse_hidden_service_port(line)
        if hidden_service:
            hidden_service = HiddenService(
                get_service_name(hidden_service),
                hidden_service,
                get_hostname(hidden_service),
            )
            services.append(hidden_service)
        elif hidden_service_port and services:
            services[-1].port_definition = hidden_service_port
    return services


async def refresh(log=True):  # pragma: no cover: used in production only
    async with utils.wait_for_redis():
        if log:
            logger.info("Refreshing hidden services list...")
        services = parse_torrc(settings.TORRC_FILE)
        services_dict = {service.name: dataclass_asdict(service) for service in services}
        anonymous_services_dict = {service.name: {"name": service.name, "hostname": service.hostname} for service in services}
        onion_host = services_dict.get("BitcartCC Merchants API", "")
        if onion_host:
            onion_host = onion_host["hostname"] or ""
        await settings.redis_pool.hmset_dict(
            REDIS_KEY,
            {
                "onion_host": onion_host,
                "services_dict": json.dumps(services_dict),
                "anonymous_services_dict": json.dumps(anonymous_services_dict),
            },
        )
        if log:
            logger.info(f"Parsed hidden services: {services}; onion_host={onion_host}")


async def get_data(key, default=None, json_decode=False):
    data = await settings.redis_pool.hget(REDIS_KEY, key, encoding="utf-8")
    data = json.loads(data) if json_decode and data else data
    return data if data else default
