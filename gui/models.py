#pylint: disable=no-member
from django.db import models
from django.utils import timezone
from embed_video.fields import EmbedVideoField
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.conf import settings
from django.contrib.auth.models import AbstractUser
import secrets
from . import tasks

# Create your models here.

class User(AbstractUser):
    is_confirmed = models.BooleanField(default=False,blank=True)

class Wallet(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=1000)
    xpub = models.CharField(max_length=1000, blank=True, default="")
    balance = models.DecimalField(max_digits=16, decimal_places=8, blank=True, default=0)
    updated_date = models.DateTimeField(default=timezone.now)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)

    class Meta:
        managed = True
        db_table = 'wallets'

    def create(self, name, user):
        self.name=name
        self.user=user
        self.id=secrets.token_urlsafe(44)
        self.save()

class Store(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=1000)
    domain = models.CharField(max_length=1000, blank=True, default="")
    template = models.CharField(max_length=1000, blank=True, default="")
    email = models.CharField(max_length=1000, blank=True, default="")
    wallet=models.ForeignKey(Wallet,on_delete=models.CASCADE)

    class Meta:
        managed = True
        db_table = 'stores'
    
    def create(self, name):
        self.name=name
        self.id=secrets.token_urlsafe(44)
        self.save()

class Product(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    amount = models.DecimalField(max_digits=16, decimal_places=8)
    quantity = models.DecimalField(max_digits=16, decimal_places=8)
    title = models.CharField(max_length=1000)
    status = models.CharField(max_length=1000,default="new")
    order_id = models.CharField(max_length=255, blank=True, default="")
    date = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(blank=True, null=True)
    video = EmbedVideoField(blank=True, null=True)
    bitcoin_address = models.CharField(max_length=255, default="")
    bitcoin_url = models.CharField(max_length=255, default="")
    store=models.ForeignKey(Store,on_delete=models.CASCADE)

    class Meta:
        managed = True
        db_table = 'products'

# This code is triggered whenever a new user has been created and saved to the database
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)

@receiver(post_save, sender=Wallet)
def create_wallet(sender, instance=None, created=False, **kwargs):
    if created:
        tasks.sync_wallet.delay(instance.id, instance.xpub)