import pytest
from gui import models

# Create your tests here.
pytestmark = pytest.mark.django_db


def test_client(client):
    user = models.User.objects.create_user(
        username="test", email="test@test.com", password="test")
    assert user.username == "test"
    assert user.email == "test@test.com"
