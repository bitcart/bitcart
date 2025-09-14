from typing import Any, cast

from dishka import AsyncContainer, FromDishka
from dishka.integrations.base import wrap_injection
from fastapi import APIRouter, HTTPException
from fastapi.security import SecurityScopes
from fastapi.websockets import WebSocket
from starlette.endpoints import WebSocketEndpoint
from starlette.status import WS_1008_POLICY_VIOLATION

from api import models, utils
from api.constants import AuthScopes
from api.invoices import InvoiceStatus
from api.redis import PubSub, Redis
from api.services.auth import AuthService
from api.services.crud import CRUDService
from api.services.crud.invoices import InvoiceService
from api.services.crud.wallets import WalletService

router = APIRouter()


def ws_endpoint_inject(func: Any) -> Any:
    return wrap_injection(
        func=func,
        is_async=True,
        container_getter=lambda args, _: args[1].state.dishka_container,
    )


class GenericWebsocketEndpoint(WebSocketEndpoint):
    NAME: str
    SERVICE_CLASS: type[CRUDService[Any]]
    REQUIRE_AUTH: bool = True
    AUTH_SCOPES: list[AuthScopes] = []

    subscriber: PubSub | None = None
    encoding = "json"

    object_service: CRUDService[Any] | None = None

    @ws_endpoint_inject
    async def on_connect(
        self,
        websocket: WebSocket,
        container: FromDishka[AsyncContainer],
        redis_pool: FromDishka[Redis],
        auth_service: FromDishka[AuthService],
    ) -> None:
        self.object_service = await container.get(self.SERVICE_CLASS)
        self.access_token = None
        self.user = None
        try:
            self.object_id = websocket.path_params["model_id"]
            if self.REQUIRE_AUTH:
                self.access_token = websocket.query_params["token"]
        except KeyError:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        if self.REQUIRE_AUTH:
            try:
                self.user, _ = await auth_service.find_user_and_check_permissions(
                    self.access_token, SecurityScopes(cast(list[str], self.AUTH_SCOPES))
                )
            except HTTPException:
                await websocket.close(code=WS_1008_POLICY_VIOLATION)
                return
        self.object = await self.object_service.get_or_none(self.object_id)
        if not self.object:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        if await self.maybe_exit_early(websocket):
            return
        self.subscriber = await utils.redis.make_subscriber(redis_pool, f"{self.NAME}:{self.object_id}")
        utils.tasks.create_task(self.poll_subs(websocket))
        await websocket.accept()

    async def poll_subs(self, websocket: WebSocket) -> None:
        async for message in utils.redis.listen_channel(cast(utils.redis.MyPubSub, self.subscriber)):
            await websocket.send_json(message)

    async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
        if self.subscriber:
            await self.subscriber.unsubscribe(f"channel:{self.NAME}:{self.object_id}")
            # TODO: handle closing more properly!

    async def maybe_exit_early(self, websocket: WebSocket) -> bool:
        return False


@router.websocket_route("/invoices/{model_id}")
class InvoiceNotify(GenericWebsocketEndpoint):
    NAME = "invoice"
    SERVICE_CLASS = InvoiceService
    REQUIRE_AUTH = False

    async def maybe_exit_early(self, websocket: WebSocket) -> bool:
        if cast(models.Invoice, self.object).status in [InvoiceStatus.EXPIRED, InvoiceStatus.COMPLETE]:
            await websocket.accept()
            await websocket.send_json(
                cast(InvoiceService, self.object_service).prepare_websocket_response(cast(models.Invoice, self.object))
            )
            await websocket.close()
            return True
        return False


@router.websocket_route("/wallets/{model_id}")
class WalletNotify(GenericWebsocketEndpoint):
    NAME = "wallet"
    SERVICE_CLASS = WalletService
    AUTH_SCOPES = [AuthScopes.WALLET_MANAGEMENT]
