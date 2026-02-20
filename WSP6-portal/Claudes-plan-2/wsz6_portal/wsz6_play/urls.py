"""wsz6_play/urls.py  –  HTTP views (join/game pages, debug redirect, echo test)."""

from django.urls import path
from . import views

app_name = 'wsz6_play'

urlpatterns = [
    path('join/<uuid:session_key>/',                        views.join_session, name='join'),
    path('game/<uuid:session_key>/<str:role_token>/',       views.game_page,    name='game_page'),
    path('game-asset/<slug:game_slug>/<path:filename>',     views.game_asset,   name='game_asset'),
    path('debug/<slug:game_slug>/',                         views.debug_launch, name='debug_launch'),
    path('echo-test/',                                      views.echo_test_page, name='echo_test'),
]
