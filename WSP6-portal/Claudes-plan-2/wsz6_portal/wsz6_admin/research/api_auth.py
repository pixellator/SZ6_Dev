"""
wsz6_admin/research/api_auth.py

DRF authentication class for per-researcher Bearer tokens.
External tools (Jupyter, R, Pandas) pass the token in the
  Authorization: Bearer <uuid-token>
header.
"""

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ResearchAPIToken


class ResearchTokenAuthentication(BaseAuthentication):
    """Authenticate via a ResearchAPIToken UUID in the Authorization header."""

    def authenticate(self, request):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return None                              # Let the next authenticator try.

        token_str = auth[7:].strip()
        try:
            token_obj = (
                ResearchAPIToken.objects
                .select_related('researcher')
                .get(token=token_str, is_active=True)
            )
        except (ResearchAPIToken.DoesNotExist, Exception):
            raise AuthenticationFailed('Invalid or inactive API token.')

        # Best-effort last_used update (non-blocking; ignore failures).
        try:
            ResearchAPIToken.objects.filter(pk=token_obj.pk).update(
                last_used=timezone.now()
            )
        except Exception:
            pass

        return (token_obj.researcher, token_obj)

    def authenticate_header(self, request):
        return 'Bearer realm="WSZ6 Research API"'
