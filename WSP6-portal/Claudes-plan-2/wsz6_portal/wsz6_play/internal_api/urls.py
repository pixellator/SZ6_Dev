"""Internal API URL routing (admin ↔ play)  –  stub for Phase 1."""
from django.urls import path
from . import views

urlpatterns = [
    path('games/installed/',              views.game_installed,      name='internal_game_installed'),
    path('games/<slug:slug>/retired/',    views.game_retired,        name='internal_game_retired'),
    path('sessions/<uuid:key>/summary/',  views.session_summary,     name='internal_session_summary'),
    path('sessions/<uuid:key>/status/',   views.session_status,      name='internal_session_status'),
    path('sessions/active/',              views.active_sessions,     name='internal_active_sessions'),
    path('sessions/<uuid:key>/observe/',  views.observe_session,     name='internal_observe_session'),
    path('launch/',                       views.launch_session,      name='internal_launch'),
    path('launch/debug/',                 views.launch_debug,        name='internal_launch_debug'),
]
