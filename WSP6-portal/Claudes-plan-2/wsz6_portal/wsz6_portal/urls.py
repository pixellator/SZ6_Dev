"""
wsz6_portal/urls.py  –  Root URL configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    # Root → dashboard
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),

    # Django built-in admin site
    path('admin/', admin.site.urls),

    # WSZ6-admin: main dashboard
    path('dashboard/', include('wsz6_admin.dashboard.urls')),

    # WSZ6-admin: per-section views
    path('accounts/', include('wsz6_admin.accounts.urls')),
    path('games/', include('wsz6_admin.games_catalog.urls')),
    path('sessions/', include('wsz6_admin.sessions_log.urls')),
    path('research/', include('wsz6_admin.research.urls')),

    # WSZ6-play: HTTP views (session join page, debug redirect, echo test)
    path('play/', include('wsz6_play.urls')),

    # Internal REST API (admin ↔ play, localhost only)
    path('internal/v1/', include('wsz6_play.internal_api.urls')),

    # External research REST API (Bearer-token or session auth)
    path('api/v1/', include('wsz6_admin.research.api_urls')),
]
