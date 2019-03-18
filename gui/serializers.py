from . import models

from rest_framework import serializers


class StoreSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Store
        fields = ("id","name","domain","template","email","wallet")

class ProductSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Product
        fields = ("id","amount","quantity","title","description","date","status","order_id","date","image","video","store")

class WalletSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Wallet
        fields = ("id","name","xpub","user")