from django.urls import path
from . import views

app_name = 'research'

urlpatterns = [
    # R1 — session list dashboard
    path('', views.research_dashboard, name='dashboard'),

    # R2 — session detail (metadata + playthrough list)
    path('sessions/<uuid:session_key>/', views.session_detail, name='session_detail'),

    # R3 — log viewer (step-by-step replay)
    path('sessions/<uuid:session_key>/<uuid:playthrough_id>/',
         views.log_viewer, name='log_viewer'),

    # Export (R5 preview — trivial to ship alongside R3)
    path('sessions/<uuid:session_key>/<uuid:playthrough_id>/export.jsonl',
         views.export_jsonl, name='export_jsonl'),
]
