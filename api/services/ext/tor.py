import asyncio
import ipaddress
import json
import os
from collections.abc import Awaitable
from dataclasses import asdict as dataclass_asdict
from dataclasses import dataclass
from typing import Any, cast

from api.logging import get_logger
from api.redis import Redis
from api.settings import Settings
from api.utils.common import run_repeated

logger = get_logger(__name__)

REDIS_KEY = "bitcart_tor_ext"


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
    port_definition: PortDefinition | None = None


class TorService:
    def __init__(self, settings: Settings, redis_pool: Redis) -> None:
        self.settings = settings
        self.redis_pool = redis_pool

    async def refresh(self, log: bool = True) -> None:  # pragma: no cover: used in production only
        services = self.parse_torrc(self.settings.TORRC_FILE, log=log)
        services_dict: dict[str, dict[str, Any]] = {service.name: dataclass_asdict(service) for service in services}
        anonymous_services_dict = {service.name: {"name": service.name, "hostname": service.hostname} for service in services}
        onion_host_info = services_dict.get("Bitcart Merchants API", {})
        onion_host = ""
        if onion_host_info:
            onion_host = onion_host_info["hostname"] or ""
        await cast(
            Awaitable[int],
            self.redis_pool.hset(
                REDIS_KEY,
                mapping={
                    "onion_host": onion_host,
                    "services_dict": json.dumps(services_dict),
                    "anonymous_services_dict": json.dumps(anonymous_services_dict),
                },
            ),
        )

    async def get_data(self, key: str, default: Any = None, json_decode: bool = False) -> Any:
        data = await cast(Awaitable[str | None], self.redis_pool.hget(REDIS_KEY, key))
        data = json.loads(data) if json_decode and data else data
        return data if data else default

    @classmethod
    def parse_torrc(cls, torrc: str | None, log: bool = True) -> list[HiddenService]:
        if not torrc:
            return []
        try:
            with open(torrc) as f:
                lines = f.readlines()
        except OSError:
            if log:
                logger.warning("Torrc file not found")
            return []
        services = []
        for line in lines:
            line = line.strip()
            hidden_service_def = cls.parse_hidden_service(line)
            hidden_service_port = cls.parse_hidden_service_port(line)
            if hidden_service_def:
                hidden_service = HiddenService(
                    cls.get_service_name(hidden_service_def),
                    hidden_service_def,
                    cast(str, cls.get_hostname(hidden_service_def, log=log)),
                )
                services.append(hidden_service)
            elif hidden_service_port and services:
                services[-1].port_definition = hidden_service_port
        return services

    @classmethod
    def get_hostname(cls, service_dir: str, log: bool = True) -> str | None:
        path = os.path.join(service_dir, "hostname")
        try:
            with open(path) as f:
                return f"http://{f.readline().strip()}"
        except OSError:
            if log:
                logger.warning(f"Hostname file missing for service {cls.get_service_name(service_dir)}")
            return None

    @staticmethod
    def get_service_name(service_dir: str) -> str:
        return os.path.basename(service_dir).replace("-", " ")

    @staticmethod
    def parse_hidden_service_port(line: str) -> PortDefinition | None:
        if not line.startswith("HiddenServicePort "):
            return None
        parts = line.split()
        if len(parts) != 3:
            return None
        try:
            virtual_port = int(parts[1].strip())
            address_port = parts[2].strip().split(":")
            if len(address_port) != 2:
                return None
            port = int(address_port[1])
            ip_address = str(ipaddress.ip_address(address_port[0].strip()))
            return PortDefinition(virtual_port, ip_address, port)
        except ValueError:
            return None  # all parsing exceptions are ValueError

    @staticmethod
    def parse_hidden_service(line: str) -> str | None:
        if not line.startswith("HiddenServiceDir "):
            return None
        parts = line.split()
        if len(parts) != 2:
            return None
        return parts[1].strip()

    @staticmethod
    def is_onion(host: str) -> bool:
        return host.lower().endswith(".onion")

    async def start(self) -> None:
        await self.refresh(log=False)
        asyncio.create_task(run_repeated(self.refresh, 60 * 10, 10))
