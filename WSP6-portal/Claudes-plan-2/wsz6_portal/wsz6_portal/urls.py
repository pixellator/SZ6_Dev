"""
wsz6_portal/urls.py  –  Root URL configuration
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Django admin site
    path('admin/', admin.site.urls),

    # WSZ6-admin: user-facing views
    path('accounts/', include('wsz6_admin.accounts.urls')),
    path('games/', include('wsz6_admin.games_catalog.urls')),
    path('sessions/', include('wsz6_admin.sessions_log.urls')),
    path('research/', include('wsz6_admin.research.urls')),

    # WSZ6-play: HTTP views (session join page, debug redirect)
    path('play/', include('wsz6_play.urls')),

    # Internal REST API (admin ↔ play)
    path('internal/v1/', include('wsz6_play.internal_api.urls')),
]
