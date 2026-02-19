"""
wsz6_portal/asgi.py

ASGI entry point. Routes HTTP requests to Django and WebSocket
connections to Django Channels consumers.
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wsz6_portal.settings.development')

# Initialize Django before importing anything that touches models / apps.
django_asgi_app = get_asgi_application()

# Import WS routing after Django is initialized.
from wsz6_play.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    # Standard HTTP → Django views
    'http': django_asgi_app,

    # WebSocket → Channels consumers (auth + origin validation)
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
