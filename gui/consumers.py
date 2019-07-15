#pylint: disable=no-member
from channels.generic.websocket import WebsocketConsumer, SyncConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.shortcuts import render, get_object_or_404, redirect, reverse
import urllib
from . import models
import json
import time


class InvoiceConsumer(WebsocketConsumer):
    def connect(self):
        self.invoice_id = self.scope["url_route"]["kwargs"]["invoice"]
        self.invoice = get_object_or_404(models.Invoice, id=self.invoice_id)
        async_to_sync(self.channel_layer.group_add)(
            self.invoice_id, self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.invoice_id, self.channel_name)

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        self.send(text_data=json.dumps({
            'message': message
        }))

    def notify(self, message):
        """message={'status':'paid'}"""
        if 'status' not in message.keys():
            raise ValueError('message must include an status key')
        self.send(text_data=json.dumps({
            'status': message["status"]
        }))


class WalletConsumer(WebsocketConsumer):
    def connect(self):
        try:
            self.wallet_id = urllib.parse.parse_qs(
                self.scope['query_string'].decode()).get("wallet", (None,))[0]
        except (KeyError, IndexError):
            self.close()
        self.wallet = get_object_or_404(models.Wallet, id=self.wallet_id)
        async_to_sync(self.channel_layer.group_add)(
            self.wallet_id, self.channel_name)
        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.wallet_id, self.channel_name)

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        self.send(text_data=json.dumps({
            'message': message
        }))

    def notify(self, message):
        """message={'status':'paid', balance:0.1}"""
        if 'status' not in message.keys():
            raise ValueError('message must include an status key')
        self.send(text_data=json.dumps({
            'status': message["status"],
            "balance": message["balance"]
        }))
