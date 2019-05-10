#pylint: disable=no-member
from django.conf import settings
from django.utils import timezone
from asgiref.sync import async_to_sync
import dramatiq
from . import models
from channels.layers import get_channel_layer
from bitcart.coins.btc import BTC
import time
import traceback


RPC_URL = settings.RPC_URL
RPC_USER = settings.RPC_USER
RPC_PASS = settings.RPC_PASS
MAX_RETRIES = 3

btc = BTC(RPC_URL)
channel_layer = get_channel_layer()


@dramatiq.actor(max_retries=MAX_RETRIES)
def poll_updates(invoice_id):
    obj = models.Product.objects.get(id=invoice_id)
    address = obj.bitcoin_address
    if not address:
        raise ValueError('Invoice not active!')
    btc_instance = BTC(RPC_URL, xpub=obj.store.wallet.xpub,
                       rpc_user=RPC_USER, rpc_pass=RPC_PASS)
    while True:
        invoice_data = btc_instance.getrequest(address)
        if invoice_data["status"] != "Pending":
            if invoice_data["status"] == "Unknown":
                obj.status = "invalid"
            if invoice_data["status"] == "Expired":
                obj.status = "expired"
            if invoice_data["status"] == "Paid":
                obj.status = "complete"
            obj.save()
            async_to_sync(channel_layer.group_send)(
                invoice_id, {"type": "notify", "status": obj.status})
            return
        time.sleep(1)


@dramatiq.actor(max_retries=0)
def sync_wallet(wallet_id, xpub):
    model = models.Wallet.objects.get(id=wallet_id)
    try:
        balance = BTC(RPC_URL, xpub=xpub, rpc_user=RPC_USER,
                      rpc_pass=RPC_PASS).balance()
        model.balance = balance["confirmed"] or 0
        model.updated_time = timezone.now()
        model.save()
        time.sleep(0.5)
        async_to_sync(channel_layer.group_send)(wallet_id, {
            "type": "notify", "status": "success", "balance": balance["confirmed"] or 0})
    except Exception:
        model.delete()
        async_to_sync(channel_layer.group_send)(
            wallet_id, {"type": "notify", "status": "error", "balance": 0})
