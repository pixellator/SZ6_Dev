"""wsz6_play/views.py  –  HTTP views for the play component."""

import mimetypes
import os
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from wsz6_play import session_store

# File extensions that may be served as game assets.
_ALLOWED_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico'}


@login_required
def join_session(request, session_key):
    """Landing page for the lobby.

    Renders the full lobby UI which opens a WebSocket to
    ``/ws/lobby/<session_key>/``.  If the session is already in progress
    the player is redirected to the game page using their role_token
    (looked up by user ID).
    """
    sk = str(session_key)
    session = session_store.get_session(sk)

    if session is None:
        return render(request, 'wsz6_play/session_not_found.html', {
            'session_key': sk,
        })

    # If game is already running and this user has a role token, redirect them.
    if session['status'] == 'in_progress':
        rm = session.get('role_manager')
        if rm:
            for player in rm.get_all_players():
                if player.user_id == request.user.id:
                    return redirect('wsz6_play:game_page', session_key=sk,
                                    role_token=player.token)

    # Paused session: show the "Resume Session" lobby page.
    is_resume = session['status'] == 'paused'

    return render(request, 'wsz6_play/join.html', {
        'session_key': sk,
        'game_name':   session.get('game_name', ''),
        'game_slug':   session.get('game_slug', ''),
        'ws_url':      f'/ws/lobby/{sk}/',
        'is_resume':   is_resume,
    })


@login_required
def game_page(request, session_key, role_token):
    """Game page: renders the game UI which opens a WebSocket to
    ``/ws/game/<session_key>/<role_token>/``.
    """
    sk = str(session_key)
    session  = session_store.get_session(sk)
    is_owner = bool(session and request.user.id == session.get('owner_id'))
    return render(request, 'wsz6_play/game.html', {
        'session_key': sk,
        'role_token':  role_token,
        'ws_url':      f'/ws/game/{sk}/{role_token}/',
        'is_owner':    is_owner,
    })


@login_required
def game_asset(request, game_slug, filename):
    """Serve a static asset (image) from a game's installed directory.

    URL: /play/game-asset/<game_slug>/<path:filename>

    Security:
      - Path traversal is blocked: the resolved path must remain inside
        the game directory.
      - Only image file extensions are served; all others return 404.
      - Requires login (assets are only needed during an active session).

    Caching:
      - Sends Cache-Control: public, max-age=86400 so the browser caches
        images across moves (important for games with many image assets).
    """
    from wsz6_admin.games_catalog.models import Game

    # Look up the game directory via the database record.
    try:
        game = Game.objects.get(slug=game_slug)
    except Game.DoesNotExist:
        raise Http404(f"No game with slug '{game_slug}'.")

    if not game.pff_path:
        raise Http404("Game has no asset directory configured.")

    # Resolve and validate the requested path.
    game_dir  = os.path.realpath(game.pff_path)
    requested = os.path.realpath(os.path.join(game_dir, filename))

    # Block path traversal: resolved path must be strictly inside game_dir.
    try:
        Path(requested).relative_to(game_dir)
    except ValueError:
        raise Http404("Invalid asset path.")

    # Only serve image file types.
    ext = os.path.splitext(requested)[1].lower()
    if ext not in _ALLOWED_IMAGE_EXTS:
        raise Http404("File type not permitted.")

    if not os.path.isfile(requested):
        raise Http404("Asset not found.")

    content_type, _ = mimetypes.guess_type(requested)
    content_type = content_type or 'application/octet-stream'

    response = FileResponse(open(requested, 'rb'), content_type=content_type)
    response['Cache-Control'] = 'public, max-age=86400'
    return response


def echo_test_page(request):
    """Phase 0: serve the WebSocket echo test HTML page."""
    return render(request, 'wsz6_play/echo_test.html', {})


@login_required
def debug_launch(request, game_slug):
    """Launch a debug session for a game (admin only) — stub for Phase 4."""
    return render(request, 'wsz6_play/debug.html', {'game_slug': game_slug})
