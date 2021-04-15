import secrets

from fastapi import APIRouter, HTTPException
from fastapi.security import SecurityScopes
from starlette.endpoints import WebSocketEndpoint
from starlette.status import WS_1008_POLICY_VIOLATION

from api import crud, models, settings, utils
from api.invoices import InvoiceStatus

router = APIRouter()


@router.websocket_route("/wallets/{model_id}")
class WalletNotify(WebSocketEndpoint):
    subscriber = None

    async def on_connect(self, websocket, **kwargs):
        await websocket.accept()
        self.channel_name = secrets.token_urlsafe(32)
        try:
            self.wallet_id = int(websocket.path_params["model_id"])
            self.access_token = websocket.query_params["token"]
        except (ValueError, KeyError):
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        try:
            self.user = await utils.authorization.AuthDependency(token=self.access_token)(
                None, SecurityScopes(["wallet_management"])
            )
        except HTTPException:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.wallet = (
            await models.Wallet.query.where(models.Wallet.id == self.wallet_id)
            .where(models.Wallet.user_id == self.user.id)
            .gino.first()
        )
        if not self.wallet:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.subscriber, self.channel = await utils.redis.make_subscriber(f"wallet:{self.wallet_id}")
        settings.loop.create_task(self.poll_subs(websocket))

    async def poll_subs(self, websocket):
        while await self.channel.wait_message():
            msg = await self.channel.get_json()
            await websocket.send_json(msg)

    async def on_disconnect(self, websocket, close_code):
        if self.subscriber:
            await self.subscriber.unsubscribe(f"channel:wallet:{self.wallet_id}")


@router.websocket_route("/invoices/{model_id}")
class InvoiceNotify(WebSocketEndpoint):
    subscriber = None

    async def on_connect(self, websocket, **kwargs):
        await websocket.accept()
        self.channel_name = secrets.token_urlsafe(32)
        try:
            self.invoice_id = int(websocket.path_params["model_id"])
        except (ValueError, KeyError):
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        self.invoice = await models.Invoice.query.where(models.Invoice.id == self.invoice_id).gino.first()
        if not self.invoice:
            await websocket.close(code=WS_1008_POLICY_VIOLATION)
            return
        if self.invoice.status in [InvoiceStatus.EXPIRED, InvoiceStatus.COMPLETE]:
            await websocket.send_json({"status": self.invoice.status})
            await websocket.close()
            return
        self.invoice = await crud.invoices.get_invoice(self.invoice_id, None, self.invoice)
        self.subscriber, self.channel = await utils.redis.make_subscriber(f"invoice:{self.invoice_id}")
        settings.loop.create_task(self.poll_subs(websocket))

    async def poll_subs(self, websocket):
        while await self.channel.wait_message():
            msg = await self.channel.get_json()
            await websocket.send_json(msg)

    async def on_disconnect(self, websocket, close_code):
        if self.subscriber:
            await self.subscriber.unsubscribe(f"channel:invoice:{self.invoice_id}")
