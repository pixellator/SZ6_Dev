from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('',         views.home,          name='home'),
    path('users/',          views.user_list,   name='user_list'),
    path('users/new/',      views.user_create, name='user_create'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('sessions-live/', views.live_sessions, name='live_sessions'),
]
