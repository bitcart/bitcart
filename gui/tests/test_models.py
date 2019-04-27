# pylint: disable=no-member
import pytest
from gui.tests.test_views import user, wallet, store
from gui import views, models
from django.shortcuts import reverse
from django.contrib.auth import authenticate
import urllib
import json
# TODO: move secrets to create method
import secrets

pytestmark = pytest.mark.django_db


def test_create_wallet(client, user):
    wallet = models.Wallet.objects.create(
        id=secrets.token_urlsafe(44), name="mywallet", user=user)
    assert wallet.name == 'mywallet'
    assert wallet.user == user


def test_create_store(client, wallet):
    store = models.Store.objects.create(
        id=secrets.token_urlsafe(44),
        name="test1", wallet=wallet, domain="example.com",
        template="default", email="test@example.com")
    assert store.name == 'test1'
    assert store.wallet == wallet
    assert store.template == 'default'


def test_create_product(client, store):
    product = models.Product.objects.create(
        id=secrets.token_urlsafe(44), amount=1.2, quantity=1,
        title='test_title', bitcoin_address='37eCSgGyN5zeumL2eHaURnC6YNdmLa9TzH',
        store=store
    )
    assert product.title == 'test_title'
    assert product.bitcoin_address == '37eCSgGyN5zeumL2eHaURnC6YNdmLa9TzH'
