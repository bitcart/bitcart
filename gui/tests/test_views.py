import pytest
from gui import views, models
from django.shortcuts import reverse
from django.contrib.auth import authenticate

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    user = models.User.objects.create_user(
        username="test", email="test@test.com", password="test")
    yield user


def test_main(client, user):
    client.login(username="test", password="test")
    assert client.get(reverse("main")).status_code == 200


def test_stores(client):
    assert True


def test_edit_store(client):
    assert True


def test_store_settings(client):
    assert True


def test_filter_products(client):
    assert True


def test_products(client):
    assert True


def test_invoice_buy(client):
    assert True


def test_product_info(client):
    assert True


def test_get_product_dict(client):
    assert True


def test_product_export(client):
    assert True


def test_create_store(client):
    assert True


def test_delete_store(client):
    assert True


def test_register(client):
    assert True


def test_login(client):
    assert True


def test_logout(client):
    assert True


def test_account_settings(client):
    assert True


def test_change_password(client):
    assert True


def test_wallets(client):
    assert True


def test_apps(client):
    assert True


def test_wallet_history(client):
    assert True


def test_locales(client):
    assert True


def test_create_product(client):
    assert True


def test_invoice_status(client):
    assert True


def test_create_wallet(client):
    assert True


def test_api_wallet_info(client):
    assert True


def test_delete_wallet(client):
    assert True
