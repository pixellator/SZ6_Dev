from django.urls import path
from . import views

app_name = 'research'

urlpatterns = [
    # R1 — session list dashboard
    path('', views.research_dashboard, name='dashboard'),

    # R2 — session detail (metadata + playthrough list)
    path('sessions/<uuid:session_key>/', views.session_detail, name='session_detail'),

    # R2 — session-level ZIP export (all play-throughs)
    path('sessions/<uuid:session_key>/export.zip',
         views.export_session_zip, name='export_session_zip'),

    # R3 — log viewer (step-by-step replay)
    path('sessions/<uuid:session_key>/<uuid:playthrough_id>/',
         views.log_viewer, name='log_viewer'),

    # R4 — artifact viewer (HTML page or JSON for AJAX)
    path('sessions/<uuid:session_key>/<uuid:playthrough_id>/artifact/<str:artifact_name>/',
         views.artifact_viewer, name='artifact_viewer'),

    # R5 — per-playthrough exports
    path('sessions/<uuid:session_key>/<uuid:playthrough_id>/export.jsonl',
         views.export_jsonl, name='export_jsonl'),
    path('sessions/<uuid:session_key>/<uuid:playthrough_id>/export.zip',
         views.export_zip, name='export_zip'),

    # R6 — annotations
    path('annotations/',                    views.annotation_list,    name='annotation_list'),
    path('annotations/add/',               views.add_annotation,     name='add_annotation'),
    path('annotations/<int:pk>/delete/',   views.delete_annotation,  name='delete_annotation'),

    # R6/R7 — API token management
    path('api-token/',          views.api_token_page,       name='api_token'),
    path('api-token/regenerate/', views.regenerate_api_token, name='regenerate_api_token'),
]
