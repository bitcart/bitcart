from starlette.websockets import WebSocketState, WebSocket
from starlette.endpoints import WebSocketEndpoint as BaseWebSocketEndpoint, status
from aioredis.pubsub import Receiver
from aioredis import Channel
import aioredis
from nejma.layers import ChannelLayer
import logging
import json
import asyncio
from datetime import datetime
from os.path import join as path_join
from typing import Callable, Dict, List, Type, Union

from bitcart_async import BTC
from fastapi import APIRouter, BackgroundTasks, HTTPException
from passlib.context import CryptContext
from pytz import utc

from . import models, settings


def now():
    return datetime.utcnow().replace(tzinfo=utc)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def authenticate_user(username: str, password: str):
    user = await models.User.query.where(models.User.username == username).gino.first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


HTTP_METHODS: List[str] = ["GET",
                           "POST",
                           "PUT",
                           "PATCH",
                           "DELETE"]


def model_view(router: APIRouter,
               path: str,
               orm_model,
               pydantic_model,
               create_model=None,
               allowed_methods: List[str] = ["GET_ONE"] + HTTP_METHODS,
               custom_methods: Dict[str, Callable] = {},
               background_tasks_mapping: Dict[str, Callable] = {}):
    if not create_model:
        create_model = pydantic_model
    response_models: Dict[str, Type] = {
        "get": List[pydantic_model],  # type: ignore
        "get_one": pydantic_model,
        "post": pydantic_model,
        "put": pydantic_model,
        "patch": pydantic_model,
        "delete": pydantic_model}

    item_path = path_join(path, "{model_id}")
    paths: Dict[str,
                str] = {"get": path,
                        "get_one": item_path,
                        "post": path,
                        "put": item_path,
                        "patch": item_path,
                        "delete": item_path}

    async def get():
        return await orm_model.query.gino.all()

    async def get_one(model_id: int):
        item = await orm_model.get(model_id)
        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"Object with id {model_id} does not exist!")
        return item

    async def post(model: create_model, background_tasks: BackgroundTasks):  # type: ignore
        obj = await orm_model.create(**model.dict())  # type: ignore
        if background_tasks_mapping.get("post"):
            background_tasks.add_task(background_tasks_mapping["post"], obj)
        return obj

    async def put(model_id: int, model: pydantic_model):  # type: ignore
        item = await get_one(model_id)
        await item.update(**model.dict()).apply()  # type: ignore
        return item

    async def patch(model_id: int, model: pydantic_model):  # type: ignore
        item = await get_one(model_id)
        await item.update(**model.dict(skip_defaults=True)).apply()  # type: ignore # noqa
        return item

    async def delete(model_id: int):
        item = await get_one(model_id)
        await item.delete()
        return item
    for method in allowed_methods:
        method_name = method.lower()
        router.add_api_route(  # type: ignore
            paths.get(method_name),
            custom_methods.get(method_name) or locals()[method_name],
            methods=[method_name if method in HTTP_METHODS else "get"],
            response_model=response_models.get(method_name))


async def get_wallet_history(model, response):
    txes = (await BTC(settings.RPC_URL, xpub=model.xpub, rpc_user=settings.RPC_USER,
                      rpc_pass=settings.RPC_PASS).history())["transactions"]
    for i in txes:
        response.append({
            "date": i["date"],
            "txid": i["txid"],
            "amount": i["value"]
        })


logger = logging.getLogger("websockets")


class RedisLayer(ChannelLayer):
    def __init__(self, redis_host, default_redis_channel_path=None):
        self.redis_host = redis_host
        self.initialized = False
        self.default_path = default_redis_channel_path or "default_path"

    async def _initialize(self):
        self.pub = await aioredis.create_redis(self.redis_host)
        self.sub = await aioredis.create_redis(self.redis_host)
        self.mpsc = Receiver(loop=asyncio.get_event_loop())
        self.initialized = True

    async def publish_to_redis(self, msg, path=None):
        if not self.initialized:
            await self._initialize()
        _path = path or self.default_path
        await self.pub.execute("publish", _path, json.dumps(msg))

    async def subscribe_to_redis(self, websocket, path=None, receive_callback=None):
        _path = path or self.default_path
        channel = Channel(_path, is_pattern=False)
        if not self.initialized:
            await self._initialize()
        try:
            result = await self.sub.subscribe(self.mpsc.channel(_path))
            async for channel, msg in self.mpsc.iter():
                if websocket.client_state == WebSocketState.CONNECTED:
                    msg = json.loads(msg)
                    if receive_callback:
                        await receive_callback(websocket, msg)
                    else:
                        await websocket.send_json(msg)
        except BaseException:
            import traceback

            traceback.print_exc()
            await self.close_connections(_path)
        finally:
            logger.info("Connection closed")

    async def close_connections(self, channel, *channels):
        await self.sub.unsubscribe(channel, *channels)
        self.mpsc.stop()
        self.pub.close()
        self.sub.close()


class RedisWebSocketEndPoint(BaseWebSocketEndpoint):
    encoding = "json"  # type: ignore

    async def dispatch(self) -> None:
        websocket = WebSocket(self.scope, receive=self.receive, send=self.send)
        await self.on_connect(websocket)
        await asyncio.gather(self._dispatch(websocket), self._redis_setup(websocket))

    async def _dispatch(self, websocket) -> None:
        close_code = status.WS_1000_NORMAL_CLOSURE

        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.receive":
                    data = await self.decode(websocket, message)
                    await self.on_receive(websocket, data)
                elif message["type"] == "websocket.disconnect":
                    close_code = int(
                        message.get(
                            "code",
                            status.WS_1000_NORMAL_CLOSURE))
                    break
        except Exception as exc:
            close_code = status.WS_1011_INTERNAL_ERROR
            raise exc from None
        finally:
            await self.on_disconnect(websocket, close_code)

    async def _redis_setup(self, websocket) -> None:
        # could be read from the app scope.
        self.channel_layer = RedisLayer(settings.REDIS_HOST)
        await self.channel_layer.subscribe_to_redis(
            websocket, receive_callback=self.on_redis_receive
        )

    async def on_redis_receive(self, websocket, data):
        # can be overidden by the user for preventing access to specific
        # clients since all clients are subscribed to the channel.

        await websocket.send_json(data)
