#pylint: disable=no-member
from django.conf import settings
from asgiref.sync import async_to_sync
from celery import shared_task
from . import models
from channels.layers import get_channel_layer
from bitcart.coins.btc import BTC
import time


RPC_URL=settings.RPC_URL
RPC_USER=settings.RPC_USER
RPC_PASS=settings.RPC_PASS

btc=BTC(RPC_URL)
channel_layer = get_channel_layer()

@shared_task
def poll_updates(invoice_id):
    obj=models.Product.objects.get(id=invoice_id)
    address=obj.bitcoin_address
    if not address:
        raise ValueError('Invoice not active!')
    btc_instance=BTC(RPC_URL, xpub=obj.store.xpub, rpc_user=RPC_USER, rpc_pass=RPC_PASS)
    while True:
        invoice_data=btc_instance.getrequest(address)
        if invoice_data["status"] != "Pending":
            if invoice_data["status"] == "Unknown":
                obj.status="invalid"  
            if invoice_data["status"] == "Expired":
                obj.status="expired"
            if invoice_data["status"] == "Paid":
                obj.status="complete"
            obj.save()
            async_to_sync(channel_layer.group_send)(
            invoice_id, {"type": "notify", "status":obj.status})
            return
        time.sleep(1)