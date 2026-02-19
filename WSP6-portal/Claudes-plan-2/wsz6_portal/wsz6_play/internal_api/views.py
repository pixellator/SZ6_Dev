"""
wsz6_play/internal_api/views.py

Internal REST API between WSZ6-admin (caller) and WSZ6-play (callee).

All endpoints authenticate via the X-Internal-Api-Key header.

Phase-2 wired endpoints:
    launch_session   — admin creates a new session; play registers it.
    active_sessions  — admin queries live session list.
    session_summary  — play updates the UARD GameSession on session end.
    session_status   — play patches the UARD GameSession status.

Phase-4 stubs (remain as stubs):
    observe_session, launch_debug
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from wsz6_play import session_store
from wsz6_play.persistence.gdm_writer import make_gdm_session_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _check_api_key(request) -> bool:
    return request.headers.get('X-Internal-Api-Key') == settings.INTERNAL_API_KEY


def _auth_error():
    return JsonResponse({'error': 'Unauthorized'}, status=401)


# ---------------------------------------------------------------------------
# Game lifecycle (admin → play)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['POST'])
def game_installed(request):
    if not _check_api_key(request):
        return _auth_error()
    data = json.loads(request.body)
    logger.info("game_installed notification: slug=%s", data.get('slug'))
    return JsonResponse({'status': 'ok', 'game_slug': data.get('slug')})


@csrf_exempt
@require_http_methods(['POST'])
def game_retired(request, slug):
    if not _check_api_key(request):
        return _auth_error()
    logger.info("game_retired notification: slug=%s", slug)
    return JsonResponse({'status': 'ok', 'slug': slug})


# ---------------------------------------------------------------------------
# Session launch (admin → play)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['POST'])
def launch_session(request):
    """Create a new lobby session in wsz6_play.

    Expected JSON body:
        {
            "game_slug":  "tic-tac-toe",
            "owner_id":   1,
            "game_name":  "Tic-Tac-Toe"      (optional; defaults to game_slug)
        }

    Returns:
        {"status": "ok", "session_key": "<uuid>", "lobby_url": "/play/join/<uuid>/"}
    """
    if not _check_api_key(request):
        return _auth_error()
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    game_slug = data.get('game_slug', '').strip()
    owner_id  = data.get('owner_id')
    game_name = data.get('game_name') or game_slug

    if not game_slug:
        return JsonResponse({'error': 'game_slug is required'}, status=400)

    session_key = str(uuid.uuid4())

    # Create the GDM session directory.
    gdm_root    = getattr(settings, 'GDM_ROOT',
                          str(settings.BASE_DIR.parent.parent / 'gdm'))
    session_dir = make_gdm_session_path(gdm_root, game_slug, session_key)
    try:
        os.makedirs(session_dir, exist_ok=True)
    except OSError as exc:
        logger.warning("launch_session: could not create GDM dir %s: %s", session_dir, exc)

    # Register in session store (role_manager is None until first lobby WS connection).
    session_store.create_session(session_key, {
        'session_key':    session_key,
        'game_slug':      game_slug,
        'game_name':      game_name,
        'owner_id':       owner_id,
        'pff_path':       os.path.join(
            getattr(settings, 'GAMES_REPO_ROOT', ''), game_slug
        ),
        'status':         'lobby',
        'role_manager':   None,
        'game_runner':    None,
        'gdm_writer':     None,
        'playthrough_id': None,
        'session_dir':    session_dir,
        'started_at':     datetime.now(timezone.utc).isoformat(),
    })

    logger.info("launch_session: session %s created for game '%s'", session_key, game_slug)
    return JsonResponse({
        'status':      'ok',
        'session_key': session_key,
        'lobby_url':   f'/play/join/{session_key}/',
    })


@csrf_exempt
@require_http_methods(['POST'])
def launch_debug(request):
    if not _check_api_key(request):
        return _auth_error()
    # TODO Phase 4: create debug session, return player URLs.
    return JsonResponse({'debug_urls': [], 'message': 'Debug launch stub.'})


# ---------------------------------------------------------------------------
# Session status (play → admin, via HTTP)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['POST'])
def session_summary(request, key):
    """Receive session summary and update UARD GameSession."""
    if not _check_api_key(request):
        return _auth_error()
    try:
        summary = json.loads(request.body)
        _update_game_session(key, summary)
    except Exception as exc:
        logger.warning("session_summary error for %s: %s", key, exc)
        return JsonResponse({'status': 'error', 'detail': str(exc)}, status=500)
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_http_methods(['PATCH'])
def session_status(request, key):
    """Update the UARD GameSession status."""
    if not _check_api_key(request):
        return _auth_error()
    try:
        data   = json.loads(request.body)
        status = data.get('status', '')
        _update_game_session_status(key, status)
    except Exception as exc:
        logger.warning("session_status error for %s: %s", key, exc)
    return JsonResponse({'status': 'ok'})


# ---------------------------------------------------------------------------
# Active sessions query (admin → play)
# ---------------------------------------------------------------------------

@require_http_methods(['GET'])
def active_sessions(request):
    if not _check_api_key(request):
        return _auth_error()
    sessions = session_store.get_all_sessions()
    active = [
        {
            'session_key': s['session_key'],
            'game_slug':   s['game_slug'],
            'game_name':   s.get('game_name', s['game_slug']),
            'status':      s['status'],
        }
        for s in sessions
        if s['status'] in ('lobby', 'in_progress')
    ]
    return JsonResponse({'sessions': active})


# ---------------------------------------------------------------------------
# Observer (stub — Phase 4)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_http_methods(['POST'])
def observe_session(request, key):
    if not _check_api_key(request):
        return _auth_error()
    # TODO Phase 4: generate observer token, return WS URL.
    return JsonResponse({
        'observer_token': 'stub-token',
        'ws_url':         f'/ws/observe/{key}/',
    })


# ---------------------------------------------------------------------------
# Private UARD helpers (synchronous ORM calls; called from HTTP request cycle)
# ---------------------------------------------------------------------------

def _update_game_session(session_key: str, summary: dict) -> None:
    from wsz6_admin.sessions_log.models import GameSession
    gs = GameSession.objects.filter(session_key=session_key).first()
    if gs is None:
        logger.warning("session_summary: GameSession %s not found", session_key)
        return
    gs.status       = GameSession.STATUS_COMPLETED
    gs.ended_at     = datetime.now(timezone.utc)
    gs.summary_json = summary
    gs.gdm_path     = summary.get('gdm_path', '')
    gs.save(update_fields=['status', 'ended_at', 'summary_json', 'gdm_path'])


def _update_game_session_status(session_key: str, status: str) -> None:
    from wsz6_admin.sessions_log.models import GameSession
    gs = GameSession.objects.filter(session_key=session_key).first()
    if gs:
        gs.status = status
        gs.save(update_fields=['status'])
