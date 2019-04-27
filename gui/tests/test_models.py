# pylint: disable=no-member
import pytest
from gui.tests.test_views import user, wallet
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
