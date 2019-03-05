from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("i/<invoice>/status/ws/", consumers.ChatConsumer),
]
