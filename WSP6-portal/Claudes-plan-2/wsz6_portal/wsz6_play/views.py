"""wsz6_play/views.py  –  HTTP views for the play component."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from wsz6_play import session_store


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

    return render(request, 'wsz6_play/join.html', {
        'session_key': sk,
        'game_name':   session.get('game_name', ''),
        'game_slug':   session.get('game_slug', ''),
        'ws_url':      f'/ws/lobby/{sk}/',
    })


@login_required
def game_page(request, session_key, role_token):
    """Game page: renders the game UI which opens a WebSocket to
    ``/ws/game/<session_key>/<role_token>/``.
    """
    sk = str(session_key)
    return render(request, 'wsz6_play/game.html', {
        'session_key': sk,
        'role_token':  role_token,
        'ws_url':      f'/ws/game/{sk}/{role_token}/',
    })


def echo_test_page(request):
    """Phase 0: serve the WebSocket echo test HTML page."""
    return render(request, 'wsz6_play/echo_test.html', {})


@login_required
def debug_launch(request, game_slug):
    """Launch a debug session for a game (admin only) — stub for Phase 4."""
    return render(request, 'wsz6_play/debug.html', {'game_slug': game_slug})
