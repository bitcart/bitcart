import asyncio
import json
import os

from aiohttp import ClientSession, WSMsgType
from aiohttp import __version__ as aiohttp_version
from aiohttp import web
from decouple import AutoConfig
from pkg_resources import parse_version
from utils import JsonResponse, authenticate, load_spec, maybe_update_key, noop_cast, parse_params

LEGACY_AIOHTTP = parse_version(aiohttp_version) < parse_version("4.0.0a0")
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = (
    "python"  # TODO: remove when all protobufs are re-generated for version 4 in electrums
)


class BaseDaemon:
    # Coin name (symbol), used for coin identification across Bitcart
    name: str
    # Base spec to use, must define jsonrpc codes and their error messages, all coins inherited use it
    BASE_SPEC_FILE: str
    # default port, must differ between daemons, in range 500X, assigned in order of coins addition to Bitcart
    DEFAULT_PORT: int
    # command aliases
    ALIASES: dict = {}

    def __init__(self):
        self.env_name = self.name.upper()
        self.env_names = set()
        self.config_getter = AutoConfig(search_path="conf")
        self.load_env()
        self.load_spec()
        # Parse all custom RPC commands
        self.supported_methods = {
            func.__name__: func for func in (getattr(self, name) for name in dir(self)) if getattr(func, "is_handler", False)
        }
        self.register_aliases()
        self.supported_methods = dict(sorted(self.supported_methods.items()))
        self.app = web.Application()
        self.configure_app()

    def register_aliases(self):
        for alias, func in self.ALIASES.items():
            self.supported_methods[alias] = self.supported_methods[func]

    def env(self, name, *, default, cast=noop_cast):
        self.env_names.add(name.lower())
        return self.config_getter(f"{self.env_name}_{name}", default=default, cast=cast)

    ### Spec support ###

    def set_dynamic_spec(self):
        pass

    def load_spec(self):
        self.spec = load_spec(self.BASE_SPEC_FILE)
        custom_spec_file = f"daemons/spec/{self.name.lower()}.json"
        if custom_spec_file != self.BASE_SPEC_FILE:
            custom_spec = load_spec(custom_spec_file, exit_on_error=False)
            maybe_update_key(self.spec, custom_spec, "electrum_map")
            maybe_update_key(self.spec, custom_spec, "exceptions")
        self.set_dynamic_spec()

    def get_error_code(self, error, fallback_code=-32603):
        """Get jsonrpc error code returned to client

        Matches error message from exceptions with loaded daemon spec
        Match performed is case-insensitive, not exact

        Args:
            error (str): error message
            fallback_code (int, optional): code to return if error is not found in the spec. Defaults to -32603.

        Returns:
            int: jsonrpc error code
        """
        error = error.lower()
        for error_message in self.spec["electrum_map"]:
            if error_message.lower() in error:
                return self.spec["electrum_map"][error_message]
        return fallback_code

    ### Base request handling ###

    def parse_xpub(self, xpub):
        if xpub is None or isinstance(xpub, str):
            return xpub, None, {}
        if isinstance(xpub, dict):
            return xpub.pop("xpub", None), xpub.pop("contract", None), xpub

    async def get_handle_request_params(self, request):
        try:
            data = await (request.json() if LEGACY_AIOHTTP else request.json(content_type=None))
        except json.decoder.JSONDecodeError:
            return None, None, None, None, None, None, None, JsonResponse(code=-32700, error="Parse error")
        method, id, params = data.get("method"), data.get("id", None), data.get("params", [])
        error = None if method else JsonResponse(code=-32601, error="Procedure not found", id=id)
        args, kwargs = parse_params(params)
        xpub, contract, extra_params = self.parse_xpub(kwargs.pop("xpub", None))
        return id, method, xpub, contract, extra_params, args, kwargs, error

    @authenticate
    async def handle_request(self, request):
        id, req_method, xpub, contract, extra_params, req_args, req_kwargs, error = await self.get_handle_request_params(
            request
        )
        if error:
            return error.send()
        return await self.execute_method(id, req_method, xpub, contract, extra_params, req_args, req_kwargs)

    @authenticate
    async def handle_websocket(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        ws.config = {"xpub": None}
        request.app["websockets"].add(ws)
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = msg.json()
                        if data.get("xpub"):
                            ws.config["xpub"] = data["xpub"]
                    except json.JSONDecodeError:
                        pass
        finally:
            request.app["websockets"].remove(ws)

    @authenticate
    async def handle_spec(self, request):
        return web.json_response(self.spec)

    def configure_app(self):
        self.app["websockets"] = set()
        self.app.router.add_post("/", self.handle_request)
        self.app.router.add_get("/ws", self.handle_websocket)
        self.app.router.add_get("/spec", self.handle_spec)
        self.app.on_startup.append(self.on_startup)
        self.app.on_shutdown.append(self.on_shutdown)

    def start(self):
        web.run_app(self.app, host=self.HOST, port=self.PORT)

    ### Websocket utilities ###

    def build_notification(self, data, xpub):
        return {"updates": [data], "wallet": xpub, "currency": self.name}

    async def notify_websockets(self, data, xpub):
        notification = self.build_notification(data, xpub)
        # If xpub is None, send global notification to all wallets regardless of notification settings
        # If xpub is not None (scoped to a specific wallet), we follow the notification settings
        coros = [
            ws.send_json(notification)
            for ws in self.app["websockets"]
            if not ws.closed and (not xpub or not ws.config["xpub"] or ws.config["xpub"] == xpub)
        ]
        await asyncio.gather(*coros)
        return True

    ### Overridable methods for completely custom coins ###

    def load_env(self):
        """Use self.env here to load all needed environment variables"""
        self.HOST = self.env(
            "HOST",
            default="0.0.0.0" if os.getenv("IN_DOCKER") else "127.0.0.1",
        )
        self.PORT = self.env("PORT", cast=int, default=self.DEFAULT_PORT)
        self.LOGIN = self.env("LOGIN", default="electrum")
        self.PASSWORD = self.env("PASSWORD", default="electrumz")
        self.DATA_PATH = self.env("DATA_PATH", default=None)
        self.VERBOSE = self.env("DEBUG", cast=bool, default=False)
        self.NET = self.env("NETWORK", default="mainnet")
        self.DEFAULT_CURRENCY = self.env("FIAT_CURRENCY", default="USD")
        self.POLLING_CAP = self.env("POLLING_CAP", cast=int, default=100)

    async def on_startup(self, app):
        """Create essential objects for daemon operation here

        Args:
            app (web.Application): aiohttp app instance
        """
        self.client_session = ClientSession()

    async def on_shutdown(self, app):
        """Gracefuly release created objects here

        Args:
            app (web.Application): aiohttp app instance
        """
        await self.client_session.close()

    async def execute_method(self, id, req_method, xpub, contract, extra_params, req_args, req_kwargs):
        """Main entrypoint for executing methods your daemon provides

        Return JsonResponse(...).send() there to avoid building message manually

        Args:
            id (int): jsonrpc id, return as is
            req_method (str): method to execute
            xpub (str): xpub of the wallet
            contract (str): smart contract address
            extra_params (dict): extra daemon-level params
            req_args (list): list of positional arguments to pass
            req_kwargs (dict): list of named arguments to pass

        Returns:
            web.Response: response containing details about method execution
        """
