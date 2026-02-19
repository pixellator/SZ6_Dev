"""
wsz6_play/routing.py

WebSocket URL routing for WSZ6-play.
"""

from django.urls import re_path
from .consumers import echo_consumer, lobby_consumer, game_consumer, observer_consumer

websocket_urlpatterns = [
    # Phase 0 echo test — verifies the Channels stack is working.
    re_path(r'ws/echo/$', echo_consumer.EchoConsumer.as_asgi()),

    # Phase 2+ game consumers (stubs for now).
    re_path(r'ws/lobby/(?P<session_key>[0-9a-f-]+)/$',
            lobby_consumer.LobbyConsumer.as_asgi()),
    re_path(r'ws/game/(?P<session_key>[0-9a-f-]+)/(?P<role_token>[^/]+)/$',
            game_consumer.GameConsumer.as_asgi()),
    re_path(r'ws/observe/(?P<session_key>[0-9a-f-]+)/$',
            observer_consumer.ObserverConsumer.as_asgi()),
]
