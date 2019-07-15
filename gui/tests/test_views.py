# pylint: disable=no-member
import pytest
from gui import views, models
from django.shortcuts import reverse
from django.contrib.auth import authenticate
import urllib
import json
# TODO: move secrets to create method
import secrets

pytestmark = pytest.mark.django_db

TEST_XPUB = "xpub6DA8GiCH7vK7VZztyyKytrXPbT755MHkwyamN3nace8ubk87ZVvFwakpF66z8AugbNJZhk2ZXSJHSytCeVHVj4pS3jjG7VcAeYzdg3VgvMr"


@pytest.fixture
def user():
    user = models.User.objects.create_user(
        username="test", email="test@test.com", password="test")
    yield user


@pytest.fixture
def wallet(user):
    wallet = models.Wallet.objects.create(
        id=secrets.token_urlsafe(44), name="mywallet", user=user, xpub=TEST_XPUB)
    yield wallet


@pytest.fixture
def store(wallet):
    store = models.Store.objects.create(
        id=secrets.token_urlsafe(44), name="mystore", domain="example.com",
        template="default", email="test@example.com", wallet=wallet)
    yield store


@pytest.fixture
def product(store):
    product = models.Product.objects.create(
        id=secrets.token_urlsafe(44),
        title="product",
        amount=5.5,
        quantity=3,
        store=store,
        description="Nice!")
    yield product


def test_truncate():
    assert views.truncate("abc", 5) == "abc"
    assert views.truncate("aaaaa", 3) == "aaa.."
    assert views.truncate("test1", 1, endchar="test2") == "ttest2"


def test_get_product_dict(product):
    data = views.get_product_dict(product)
    assert isinstance(data, dict)
    assert data['amount'] == 5.5
    assert data['quantity'] == 3
    assert data['title'] == 'product'
    assert data['description'] == 'Nice!'


def test_main(client, user):
    client.login(username="test", password="test")
    assert client.get(reverse("main")).status_code == 200


def test_noauth(client):
    url = urllib.parse.urlparse(client.get(
        reverse("main"), follow=True).redirect_chain[-1][0]).path
    assert url == reverse("login")


def test_stores(client, user, wallet):
    client.login(username="test", password="test")
    kwargs = {"name": "test1", "wallet": wallet.pk, "domain": "example.com",
              "template": "default", "email": "test@example.com"}
    client.post(reverse("stores"), json.dumps(
        kwargs), content_type='application/json')
    assert models.Store.objects.filter(**kwargs).exists()


def test_delete_wallet(client, wallet):
    client.login(username='test', password='test')
    kwargs = {"wallet": wallet.pk}
    client.post(reverse("delete_wallet", kwargs=kwargs))
    assert not models.Wallet.objects.filter(pk=wallet.pk).exists()
