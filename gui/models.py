#pylint: disable=no-member
from django.db import models
from django.utils import timezone
from embed_video.fields import EmbedVideoField
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.conf import settings
from django.contrib.auth.models import User
import secrets

# Create your models here.

class Store(models.Model):
    FEE_CHOICES=(
        (1,"... only if the customer makes more than one payment for the invoice"),
        (2,"Always"),
        (3,"Never")
    )
    id = models.CharField(max_length=255, primary_key=True)
    can_delete = models.IntegerField(default=1, blank=True)
    name = models.CharField(max_length=1000)
    website = models.CharField(max_length=1000, blank=True, default="")
    can_invoice = models.BooleanField(default=False)
    xpub = models.CharField(max_length=1000, blank=True, default="")
    invoice_expire = models.IntegerField(default=15)
    fee_mode = models.IntegerField(default=1,choices=FEE_CHOICES)
    payment_tolerance = models.FloatField(default=0)
    user=models.ForeignKey(User,on_delete=models.CASCADE)

    class Meta:
        managed = True
        db_table = 'stores'


    def create(self, name, user):
        self.name=name
        self.user=user
        self.id=secrets.token_urlsafe(44)
        self.save()

class Product(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    amount = models.FloatField()
    quantity = models.FloatField()
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
