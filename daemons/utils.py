import asyncio
import dataclasses
import inspect
import json
import logging
import sys
import time
import traceback
from abc import ABCMeta, abstractmethod
from base64 import b64decode
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from aiohttp import web

CONVERT_RATE = 100000000


def noop_cast(v):
    return v


def format_satoshis(x):
    return f"{(Decimal(x) / CONVERT_RATE):.08f}"


def load_spec(spec_file, exit_on_error=True):
    try:
        with open(spec_file) as f:
            return json.loads(f.read())
    except (OSError, json.JSONDecodeError) as e:
        if exit_on_error:
            sys.exit(e)
        return {}


def maybe_update_key(dest, other, key):
    other_value = other.get(key, {})
    if key in dest:
        dest[key].update(other_value)
    else:
        dest[key] = other_value


def rpc(f=None, requires_wallet=False, requires_network=False, requires_lightning=False):
    def wrapper(f):
        f.is_handler = True
        f.requires_wallet = bool(requires_wallet)
        f.requires_network = bool(requires_network)
        f.requires_lightning = bool(requires_lightning)
        return f

    if f:
        return wrapper(f)
    return wrapper


def authenticate(f):
    async def wrapper(daemon, request):
        auth = request.headers.get("Authorization")
        user, password = decode_auth(auth)
        if not (user == daemon.LOGIN and password == daemon.PASSWORD):
            return JsonResponse(code=-32600, error="Unauthorized").send()
        return await f(daemon, request)

    return wrapper


def cached(f):
    def wrapper(*args, **kwargs):
        if hasattr(f, "cache"):
            return f.cache
        result = f(*args, **kwargs)
        f.cache = result
        return result

    return wrapper


def decode_auth(authstr):
    if not authstr:
        return None, None
    authstr = authstr.replace("Basic ", "")
    decoded_str = b64decode(authstr).decode("latin1")
    user, password = decoded_str.split(":")
    return user, password


def parse_params(params):
    args = params
    kwargs = {}
    if isinstance(params, list):
        if len(params) > 0 and isinstance(params[-1], dict):
            kwargs = params.pop()
    elif isinstance(params, dict):
        kwargs = params
        args = ()
    return args, kwargs


def get_exception_message(e):
    return traceback.format_exception_only(type(e), e)[-1].strip()


@contextmanager
def hide_logging_errors(enable):
    if enable:
        logging.disable(logging.ERROR)
    yield
    if enable:
        logging.disable(logging.NOTSET)


@dataclass
class JsonResponse:
    id: Optional[int] = None
    code: Optional[int] = None
    error: Optional[str] = None
    result: Optional[Any] = None

    def send(self):
        if self.result is not None and self.error is not None:
            raise ValueError(f"result={self.result} and error={self.error} cannot be both set")
        if self.error is not None:
            return self.send_error_response()
        else:
            return self.send_ok_response()

    def send_error_response(self):
        return web.json_response({"jsonrpc": "2.0", "error": {"code": self.code, "message": self.error}, "id": self.id})

    def send_ok_response(self):
        return web.json_response({"jsonrpc": "2.0", "result": self.result, "id": self.id})


async def periodic_task(self, process_func, interval):
    while self.running:
        start = time.time()
        try:
            await process_func()
        except Exception:
            if self.VERBOSE:
                print(traceback.format_exc())
        elapsed = time.time() - start
        await asyncio.sleep(max(interval - elapsed, 0))


class CastingDataclass:
    def __post_init__(self):
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if (
                not isinstance(value, field.type)
                and field.default is dataclasses.MISSING
                and field.default_factory is dataclasses.MISSING
            ):
                setattr(self, field.name, field.type(value))


def load_json_dict(s, error_message):
    json_dict = s
    if isinstance(s, str):
        try:
            json_dict = json.loads(s)
        except json.JSONDecodeError as e:
            raise Exception(error_message) from e
    return json_dict


def is_int(v):
    try:
        int(v)
        return True
    except Exception:
        return False


def try_cast_num(v):
    if is_int(v):
        return int(v)
    return v


def get_func_name(func):
    if hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func.__name__


def exception_retry_middleware(make_request, errors, verbose, retries=5):
    async def middleware(*args, **kwargs):
        for i in range(retries):
            try:
                result = await make_request(*args, **kwargs)
                if "error" in result and result["error"].get("code") == -32603:  # Internal error
                    raise ValueError(result["error"])
                return result
            except errors:
                if i < retries - 1:
                    if verbose:
                        print(f"Retrying {get_func_name(make_request)} {args} {kwargs}, attempt {i + 1}")
                    await asyncio.sleep(1)
                    continue
                else:
                    if verbose:
                        print(f"Failed after {retries} retries: {get_func_name(make_request)} {args} {kwargs}")
                    raise

    return middleware


def async_partial(async_fn, *wrap_args):
    async def wrapped(*args, **kwargs):
        return await async_fn(*wrap_args, *args, **kwargs)

    wrapped.__wrapped__ = async_fn
    return wrapped


def get_function_header(func, func_obj):
    signature = inspect.signature(func_obj)
    vals = list(signature.parameters.values())
    found_idx = None
    for idx, val in enumerate(vals):
        if val.name == "wallet":
            found_idx = idx
            break
    if found_idx is not None:
        vals.pop(found_idx)
    signature = inspect.Signature(parameters=vals, return_annotation=signature.return_annotation)
    doc = inspect.getdoc(func_obj)
    s = f"{func}{signature}"
    if doc is not None:
        s += f"\n\n{doc}"
    return s


def modify_payment_url(key, url, amount):
    if not Decimal(amount):
        return url
    parsed = urlparse(url)
    qs = dict(parse_qsl(parsed.query))
    qs[key] = amount
    parsed = parsed._replace(query=urlencode(qs))
    return urlunparse(parsed)


class AbstractRPCProvider(metaclass=ABCMeta):
    @abstractmethod
    async def send_single_request(self, *args, **kwargs):
        pass

    @abstractmethod
    async def send_ping_request(self):
        pass


class MultipleProviderRPC(metaclass=ABCMeta):
    providers: list[AbstractRPCProvider]

    NEXT_RPC_SWITCH_TIMES = 5
    RPC_UP_CHECK_TIMES = 5
    CHECK_STABLE_RPC_INTERVAL = 5 * 60

    RESET = object()  # sentinel

    def __init__(self, providers: list[AbstractRPCProvider]):
        assert isinstance(providers, list)
        self.providers = providers
        if not self.providers:
            raise ValueError("No urls provided")
        self.current_rpc_idx = 0
        self.failed_stats = [0 for _ in self.providers]
        self.switch_lock = asyncio.Lock()
        self.locks = [asyncio.Lock() for _ in self.providers]
        self.running = False

    @property
    def current_rpc(self):
        return self.providers[self.current_rpc_idx]

    def prev_rpc_idx(self, idx):
        return (idx - 1) % len(self.providers)

    def next_rpc_idx(self, idx):
        return (idx + 1) % len(self.providers)

    async def prev_rpc(self):
        async with self.switch_lock:
            await self._edit_failed_stats(self.current_rpc_idx)
            self.current_rpc_idx = self.prev_rpc_idx(self.current_rpc_idx)
            return self.current_rpc

    async def next_rpc(self):
        async with self.switch_lock:
            await self._edit_failed_stats(self.current_rpc_idx)
            self.current_rpc_idx = self.next_rpc_idx(self.current_rpc_idx)
            return self.current_rpc

    def is_last_rpc(self):
        return self.current_rpc_idx == len(self.providers) - 1

    async def _edit_failed_stats(self, idx, delta=RESET):
        async with self.locks[idx]:
            if delta is self.RESET:
                self.failed_stats[idx] = 0
            else:
                self.failed_stats[idx] = max(0, self.failed_stats[idx] + delta)

    async def send_request(self, *args, **kwargs):
        has_exception = False
        try:
            start_rpc_idx = self.current_rpc_idx
            rpc_idx = start_rpc_idx
            while True:
                try:
                    return await self.providers[rpc_idx].send_single_request(*args, **kwargs)
                except Exception:
                    await self._edit_failed_stats(rpc_idx, +1)
                    if self.failed_stats[rpc_idx] > self.NEXT_RPC_SWITCH_TIMES:
                        await self.next_rpc()
                    rpc_idx = self.next_rpc_idx(rpc_idx)
                    if rpc_idx == start_rpc_idx:
                        raise
        except Exception:
            has_exception = True
            raise
        finally:
            if not has_exception:
                await self._edit_failed_stats(rpc_idx, -1)

    async def maintain_stable_rpc(self):
        while self.running:
            await asyncio.sleep(self.CHECK_STABLE_RPC_INTERVAL)
            prev_idx = self.current_rpc_idx - 1
            if prev_idx < 0:
                continue
            is_stable = True
            for _ in range(0, self.RPC_UP_CHECK_TIMES + 1):
                try:
                    await self.providers[prev_idx].send_ping_request()
                except Exception:
                    is_stable = False
                    break
            if is_stable:
                await self.prev_rpc()

    async def start(self):
        self.running = True
        asyncio.ensure_future(self.maintain_stable_rpc())

    async def stop(self):
        self.running = False
