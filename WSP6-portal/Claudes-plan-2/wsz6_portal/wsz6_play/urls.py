"""wsz6_play/urls.py  –  HTTP views (join page, debug redirect)."""
from django.urls import path
from . import views

app_name = 'wsz6_play'

urlpatterns = [
    path('join/<uuid:session_key>/', views.join_session, name='join'),
    path('debug/<slug:game_slug>/', views.debug_launch,  name='debug_launch'),
    path('echo-test/', views.echo_test_page,             name='echo_test'),
]
