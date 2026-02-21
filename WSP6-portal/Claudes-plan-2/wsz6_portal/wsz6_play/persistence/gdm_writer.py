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
    artifact_created    — artifact_name, artifact_path, version
    artifact_saved      — artifact_name, artifact_path, version
    artifact_finalized  — artifact_name, artifact_path, final_version

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
                    <name>.txt          ← current (latest) version
                    <name>.v1.txt       ← first explicit save
                    <name>.v2.txt       ← second explicit save
                    ...
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path


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
        self.playthrough_dir = playthrough_dir
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

    # -----------------------------------------------------------------------
    # Artifact support (R4)
    # -----------------------------------------------------------------------

    async def write_artifact(
        self,
        artifact_name: str,
        content: str,
        version: int,
    ) -> str:
        """Write artifact content to a versioned file in artifacts/.

        Writes two files:
          - ``<name>.v<N>.txt``  — the versioned snapshot (immutable reference)
          - ``<name>.txt``       — the current (latest) copy (overwritten each time)

        Returns the relative path of the versioned file (e.g. ``artifacts/essay.v2.txt``).
        """
        artifacts_dir = os.path.join(self.playthrough_dir, 'artifacts')
        versioned_name = f"{artifact_name}.v{version}.txt"
        versioned_path = os.path.join(artifacts_dir, versioned_name)
        current_path   = os.path.join(artifacts_dir, f"{artifact_name}.txt")
        await asyncio.to_thread(self._write_text, versioned_path, content)
        await asyncio.to_thread(self._write_text, current_path, content)
        return os.path.join('artifacts', versioned_name)

    async def write_artifact_event(
        self,
        event_type: str,
        artifact_name: str,
        artifact_path: str,
        version: int,
    ) -> None:
        """Log an artifact event to the JSONL log.

        ``event_type`` should be one of:
            ``artifact_created``, ``artifact_saved``, ``artifact_finalized``
        ``artifact_path`` is the relative path returned by ``write_artifact()``.
        """
        extra = {
            'artifact_name': artifact_name,
            'artifact_path': artifact_path,
        }
        if event_type == 'artifact_finalized':
            extra['final_version'] = version
        else:
            extra['version'] = version
        await self.write_event(event_type, **extra)

    def _write_text(self, path: str, content: str) -> None:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
