import secrets

from fastapi import APIRouter, HTTPException
from fastapi.security import SecurityScopes
from starlette.endpoints import WebSocketEndpoint
from starlette.status import WS_1008_POLICY_VIOLATION

from api import crud, models, settings, utils
from api.invoices import InvoiceStatus

router = APIRouter()


class GenericWebsocketEndpoint(WebSocketEndpoint):
    NAME: str
    MODEL: models.db.Model
    REQUIRE_AUTH: bool = True

    subscriber = None

    async def on_connect(self, websocket, **kwargs):
        await websocket.accept()
        self.channel_name = secrets.token_urlsafe(32)
        self.access_token = None
        self.user = None
        try:
            self.object_id = int(websocket.path_params["model_id"])
            if self.REQUIRE_AUTH:
                self.access_token = websocket.query_params["token"]
        except (ValueError, KeyError):
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        if self.REQUIRE_AUTH:
            try:
                self.user = await utils.authorization.AuthDependency(token=self.access_token)(
                    None, SecurityScopes([f"{self.NAME}_management"])
                )
            except HTTPException:
                await websocket.close(code=WS_1008_POLICY_VIOLATION)
                return
        self.object = self.MODEL.query.where(self.MODEL.id == self.object_id)
        if self.REQUIRE_AUTH:
            self.object = self.object.where(self.MODEL.user_id == self.user.id)
        self.object = await self.object.gino.first()
        if not self.object:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        if await self.maybe_exit_early(websocket):
            return
        self.object = await self.load_object()
        self.subscriber, self.channel = await utils.redis.make_subscriber(f"{self.NAME}:{self.object_id}")
        settings.loop.create_task(self.poll_subs(websocket))

    async def poll_subs(self, websocket):
        while await self.channel.wait_message():
            msg = await self.channel.get_json()
            await websocket.send_json(msg)

    async def on_disconnect(self, websocket, close_code):
        if self.subscriber:
            await self.subscriber.unsubscribe(f"channel:{self.NAME}:{self.object_id}")

    async def maybe_exit_early(self, websocket):
        return False

    async def load_object(self):
        return self.object


@router.websocket_route("/wallets/{model_id}")
class WalletNotify(GenericWebsocketEndpoint):
    NAME = "wallet"
    MODEL = models.Wallet


@router.websocket_route("/invoices/{model_id}")
class InvoiceNotify(GenericWebsocketEndpoint):
    NAME = "invoice"
    MODEL = models.Invoice
    REQUIRE_AUTH = False

    async def maybe_exit_early(self, websocket):
        if self.object.status in [InvoiceStatus.EXPIRED, InvoiceStatus.COMPLETE]:
            await websocket.send_json({"status": self.object.status})
            await websocket.close()
            return True
        return False

    async def load_object(self):
        return await crud.invoices.get_invoice(self.object_id, None, self.object)
