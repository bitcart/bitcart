#pylint: disable=no-member
from . import models
from . import serializers
from rest_framework import viewsets, permissions


class StoreViewSet(viewsets.ModelViewSet):
    """ViewSet for the Store class"""

    queryset = models.Store.objects.all()
    serializer_class = serializers.StoreSerializer
    permission_classes = [permissions.IsAuthenticated]

class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for the Product class"""

    queryset = models.Product.objects.all()
    serializer_class = serializers.ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

class WalletViewSet(viewsets.ModelViewSet):
    """ViewSet for the Product class"""

    queryset = models.Wallet.objects.all()
    serializer_class = serializers.WalletSerializer
    permission_classes = [permissions.IsAuthenticated]