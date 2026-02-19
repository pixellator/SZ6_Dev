from django.urls import path
from . import views

app_name = 'games_catalog'

urlpatterns = [
    path('',              views.game_list,    name='list'),
    path('install/',      views.game_install, name='install'),
    path('<slug:slug>/',  views.game_detail,  name='detail'),
]
