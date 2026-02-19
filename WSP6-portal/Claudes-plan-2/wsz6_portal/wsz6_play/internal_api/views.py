"""
wsz6_play/internal_api/views.py

Internal REST API between WSZ6-admin and WSZ6-play.
All endpoints require the INTERNAL_API_KEY header.
Stubs return 200 OK; full implementation in Phase 1/2.
"""

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json


def _check_api_key(request):
    """Return True if the request carries the correct internal API key."""
    return request.headers.get('X-Internal-Api-Key') == settings.INTERNAL_API_KEY


def _auth_error():
    return JsonResponse({'error': 'Unauthorized'}, status=401)


@csrf_exempt
@require_http_methods(['POST'])
def game_installed(request):
    if not _check_api_key(request): return _auth_error()
    # TODO (Phase 1): load formulation, cache it for session creation.
    data = json.loads(request.body)
    return JsonResponse({'status': 'ok', 'game_slug': data.get('slug')})


@csrf_exempt
@require_http_methods(['POST'])
def game_retired(request, slug):
    if not _check_api_key(request): return _auth_error()
    # TODO (Phase 1): mark game as unavailable for new sessions.
    return JsonResponse({'status': 'ok', 'slug': slug})


@csrf_exempt
@require_http_methods(['POST'])
def session_summary(request, key):
    if not _check_api_key(request): return _auth_error()
    # TODO (Phase 2): write summary to UARD GameSession record.
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_http_methods(['PATCH'])
def session_status(request, key):
    if not _check_api_key(request): return _auth_error()
    # TODO (Phase 2): update GameSession.status in UARD.
    return JsonResponse({'status': 'ok'})


@require_http_methods(['GET'])
def active_sessions(request):
    if not _check_api_key(request): return _auth_error()
    # TODO (Phase 2): return list of active session keys from wsz6_play.
    return JsonResponse({'sessions': []})


@csrf_exempt
@require_http_methods(['POST'])
def observe_session(request, key):
    if not _check_api_key(request): return _auth_error()
    # TODO (Phase 4): generate observer token, return WS URL.
    return JsonResponse({'observer_token': 'stub-token', 'ws_url': f'/ws/observe/{key}/'})


@csrf_exempt
@require_http_methods(['POST'])
def launch_session(request):
    if not _check_api_key(request): return _auth_error()
    # TODO (Phase 2): create session, return session_key + lobby URL.
    import uuid
    session_key = str(uuid.uuid4())
    return JsonResponse({'session_key': session_key, 'lobby_url': f'/play/join/{session_key}/'})


@csrf_exempt
@require_http_methods(['POST'])
def launch_debug(request):
    if not _check_api_key(request): return _auth_error()
    # TODO (Phase 4): create debug session, return player URLs.
    return JsonResponse({'debug_urls': [], 'message': 'Debug launch stub.'})
