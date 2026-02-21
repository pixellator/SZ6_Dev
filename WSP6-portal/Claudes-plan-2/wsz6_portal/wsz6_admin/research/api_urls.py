"""
wsz6_admin/research/api_urls.py

URL patterns for the external research REST API.
Mounted at /api/v1/ in the root urls.py.
"""

from django.urls import path
from . import api_views

urlpatterns = [
    # Session list / detail
    path(
        'sessions/',
        api_views.APISessionListView.as_view(),
        name='api_session_list',
    ),
    path(
        'sessions/<uuid:session_key>/',
        api_views.APISessionDetailView.as_view(),
        name='api_session_detail',
    ),

    # Play-through list / detail
    path(
        'sessions/<uuid:session_key>/playthroughs/',
        api_views.APIPlayThroughListView.as_view(),
        name='api_playthrough_list',
    ),
    path(
        'sessions/<uuid:session_key>/playthroughs/<uuid:playthrough_id>/',
        api_views.APIPlayThroughDetailView.as_view(),
        name='api_playthrough_detail',
    ),

    # Log endpoints
    path(
        'sessions/<uuid:session_key>/playthroughs/<uuid:playthrough_id>/log/',
        api_views.APILogView.as_view(),
        name='api_log',
    ),
    path(
        'sessions/<uuid:session_key>/playthroughs/<uuid:playthrough_id>/log.jsonl',
        api_views.APILogRawView.as_view(),
        name='api_log_jsonl',
    ),
]
