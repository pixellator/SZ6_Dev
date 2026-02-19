"""
wsz6_play/persistence/gdm_writer.py

Append-only JSONL event log writer for one play-through (GDM storage).

Log format — one JSON object per line:

    {"t": "<ISO8601>", "event": "<type>", ...extra fields...}

Supported event types (write_event is generic; these are conventions):
    game_started        — role_assignments, session_key
    operator_applied    — step, op_index, op_name, args, role_num
    undo_applied        — step
    game_ended          — outcome, goal_message/reason, step
    player_joined       — name, role_num
    player_left         — name

GDM directory layout:
    <gdm_root>/
      <game_slug>/
        sessions/
          <session_key>/           ← session_dir
            playthroughs/
              <playthrough_id>/    ← playthrough_dir
                log.jsonl
                checkpoints/
                artifacts/
"""

import asyncio
import json
import os
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def make_gdm_session_path(gdm_root: str, game_slug: str, session_key: str) -> str:
    """Return the absolute path for the GDM session directory."""
    return os.path.join(gdm_root, game_slug, 'sessions', session_key)


def make_gdm_playthrough_path(session_dir: str, playthrough_id: str) -> str:
    """Return the absolute path for a specific play-through directory."""
    return os.path.join(session_dir, 'playthroughs', playthrough_id)


def ensure_gdm_dirs(playthrough_dir: str) -> None:
    """Create the play-through directory tree (including checkpoints/artifacts)."""
    os.makedirs(os.path.join(playthrough_dir, 'checkpoints'), exist_ok=True)
    os.makedirs(os.path.join(playthrough_dir, 'artifacts'), exist_ok=True)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class GDMWriter:
    """Async-safe append-only JSONL writer for one play-through."""

    def __init__(self, playthrough_dir: str):
        self.log_path = os.path.join(playthrough_dir, 'log.jsonl')
        self._lock = asyncio.Lock()

    async def write_event(self, event_type: str, **kwargs) -> None:
        """Append one event record to the JSONL log.

        The record always includes:
            ``t``     — ISO 8601 UTC timestamp
            ``event`` — the event_type string
        Additional keyword arguments are included verbatim.
        """
        record = {
            't':     datetime.now(timezone.utc).isoformat(),
            'event': event_type,
            **kwargs,
        }
        line = json.dumps(record, default=str) + '\n'
        async with self._lock:
            await asyncio.to_thread(self._append, line)

    def _append(self, line: str) -> None:
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(line)
