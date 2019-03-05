from . import models

from rest_framework import serializers


class StoreSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Store
        fields = ("id","name","website","can_invoice","xpub","invoice_expire","fee_mode","payment_tolerance","user")

class ProductSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Product
        fields = ("id","amount","quantity","title","description","date","status","order_id","date","image","video","store")

