"""
wsz6_play/session_store.py

In-process registry of active game sessions.

Phase-2 design (single-process, InMemoryChannelLayer):
    Sessions are stored in a module-level dict protected by a
    threading.Lock().  Lock acquisition is fast (microseconds), making it
    safe to call from both sync (HTTP views) and async (WS consumers)
    code without blocking the event loop.

Phase-7 upgrade path:
    Replace _sessions with a Redis-backed store so the registry survives
    worker restarts and scales across multiple Daphne processes.

Session dict structure
----------------------
session_key     str                 UUID string
game_slug       str                 e.g. "tic-tac-toe"
game_name       str                 e.g. "Tic-Tac-Toe"
owner_id        int | None          Django user ID of session owner
pff_path        str                 Absolute path to game directory
status          str                 'lobby' | 'in_progress' | 'ended'
role_manager    RoleManager | None  None until first lobby connection
game_runner     GameRunner | None   None until game starts
gdm_writer      GDMWriter | None    None until game starts
playthrough_id  str | None          UUID hex; set when game starts
session_dir     str                 Absolute path to GDM session directory
started_at      str                 ISO 8601 UTC timestamp
"""

import threading

_sessions: dict = {}
_lock = threading.Lock()


def create_session(session_key: str, data: dict) -> None:
    """Register a new session."""
    with _lock:
        _sessions[session_key] = data


def get_session(session_key: str) -> dict | None:
    """Return the session dict, or None if not found."""
    with _lock:
        return _sessions.get(session_key)


def update_session(session_key: str, updates: dict) -> None:
    """Merge ``updates`` into an existing session dict."""
    with _lock:
        if session_key in _sessions:
            _sessions[session_key].update(updates)


def delete_session(session_key: str) -> None:
    """Remove a session from the store."""
    with _lock:
        _sessions.pop(session_key, None)


def get_all_sessions() -> list:
    """Return a snapshot list of all session dicts."""
    with _lock:
        return list(_sessions.values())
