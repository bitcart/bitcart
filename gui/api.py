#pylint: disable=no-member
from . import models
from . import serializers
from .views import truncate
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from bitcart.coins.btc import BTC
from django.conf import settings
import decimal

RPC_USER = settings.RPC_USER
RPC_PASS = settings.RPC_PASS

RPC_URL = settings.RPC_URL

PRECISION = decimal.Decimal('0.00000001')


class StoreViewSet(viewsets.ModelViewSet):
    """ViewSet for the Store class"""

    queryset = models.Store.objects.all()
    serializer_class = serializers.StoreSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Optionally restricts the returned purchases to a given user,
        by filtering against a `domain` query parameter in the URL.
        """
        queryset = models.Store.objects.all()
        domain = self.request.query_params.get('domain', None)
        if domain is not None:
            queryset = queryset.filter(domain=domain)
        return queryset


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for the Product class"""

    queryset = models.Product.objects.all().order_by("-date")
    serializer_class = serializers.ProductSerializer
    permission_classes = [permissions.IsAuthenticated]


class InvoiceViewSet(viewsets.ModelViewSet):
    """ViewSet for the Invoice class"""

    queryset = models.Invoice.objects.all().order_by("-date")
    serializer_class = serializers.InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = models.Invoice.objects.all().order_by("-date")
        status = self.request.query_params.get('status', None)
        if status is not None:
            queryset = queryset.filter(status=status)
        currency = self.request.query_params.get('currency', 'BTC')
        if currency == "USD":
            exchange_rate = decimal.Decimal(
                BTC(RPC_URL, rpc_user=RPC_USER, rpc_pass=RPC_PASS).server.exchange_rate())
            for i in queryset:
                i.amount = (decimal.Decimal(i.amount) *
                            exchange_rate).quantize(PRECISION)
        return queryset


class WalletViewSet(viewsets.ModelViewSet):
    """ViewSet for the Product class"""

    queryset = models.Wallet.objects.all()
    serializer_class = serializers.WalletSerializer
    permission_classes = [permissions.IsAuthenticated]


class USDPriceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, format=None):
        btc_amount = decimal.Decimal(request.query_params.get("btc", 1))
        usd_price = decimal.Decimal(
            BTC(RPC_URL, rpc_user=RPC_USER, rpc_pass=RPC_PASS).server.exchange_rate())
        usd_price = (
            btc_amount * usd_price).quantize(PRECISION)
        return Response(usd_price)


def get_wallet_history(model, response):
    txes = BTC(RPC_URL, xpub=model.xpub, rpc_user=RPC_USER,
               rpc_pass=RPC_PASS).server.history()["transactions"]
    for i in txes:
            #response.append([i["date"], truncate(i["txid"], 20), i["value"]])
        response.append({
            "date": i["date"],
            "txid": truncate(i["txid"], 20),
            "amount": i["value"]
        })


class WalletHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, wallet, format=None):
        response = []
        if wallet == "0":
            for model in models.Wallet.objects.filter(user=request.user):
                get_wallet_history(model, response)
        else:
            model = get_object_or_404(models.Wallet, id=wallet)
            get_wallet_history(model, response)

        return Response(response)
