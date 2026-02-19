"""wsz6_play/views.py  –  HTTP views stubs."""
from django.shortcuts import render

def join_session(request, session_key):
    """Landing page for invited players to join a lobby."""
    # TODO (Phase 2): validate session_key, render lobby page.
    return render(request, 'wsz6_play/join.html', {'session_key': session_key})

def echo_test_page(request):
    """Phase 0: serve the WebSocket echo test HTML page."""
    from django.shortcuts import render
    return render(request, 'wsz6_play/echo_test.html', {})

def debug_launch(request, game_slug):
    """Launch a debug session for a game (admin only)."""
    # TODO (Phase 4): create debug session, return multi-tab debug view.
    return render(request, 'wsz6_play/debug.html', {'game_slug': game_slug})
