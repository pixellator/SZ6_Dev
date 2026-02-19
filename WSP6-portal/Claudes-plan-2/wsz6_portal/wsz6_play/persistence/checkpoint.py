"""
wsz6_play/persistence/checkpoint.py

Save and load game state checkpoints for the pause/resume feature.

File layout:
    <playthrough_dir>/checkpoints/<checkpoint_id>.json

Checkpoint JSON format:
    {
      "checkpoint_id":   "<uuid hex>",
      "playthrough_id":  "<uuid hex>",
      "session_key":     "<uuid>",
      "step":            <int>,
      "label":           "<str>",
      "state":           { ...serialize_state output... },
      "role_assignments": { ...rm.to_dict() output... }
    }
"""

import asyncio
import json
import logging
import os
import uuid

from channels.db import database_sync_to_async

from wsz6_play.engine.state_serializer import deserialize_state, serialize_state
from wsz6_play.persistence.gdm_writer import make_gdm_playthrough_path

logger = logging.getLogger(__name__)


async def save_checkpoint(session: dict, runner, label: str = '') -> str:
    """Serialize current state to disk and create a Checkpoint DB row.

    Args:
        session:  The session dict from the session store.
        runner:   The active GameRunner instance.
        label:    Human-readable label for this checkpoint (e.g. 'pause').

    Returns:
        The checkpoint_id (UUID hex string).
    """
    checkpoint_id  = uuid.uuid4().hex
    playthrough_id = session['playthrough_id']
    session_dir    = session['session_dir']
    pt_dir         = make_gdm_playthrough_path(session_dir, playthrough_id)
    file_path      = os.path.join(pt_dir, 'checkpoints', f'{checkpoint_id}.json')

    rm = session['role_manager']
    data = {
        'checkpoint_id':    checkpoint_id,
        'playthrough_id':   playthrough_id,
        'session_key':      str(session.get('session_key', '')),
        'step':             runner.step,
        'label':            label,
        'state':            serialize_state(runner.current_state),
        'role_assignments': rm.to_dict(),
    }

    await asyncio.to_thread(_write_json, file_path, data)
    await _create_checkpoint_record(
        playthrough_id=playthrough_id,
        checkpoint_id=checkpoint_id,
        file_path=file_path,
        step_number=runner.step,
        label=label,
    )

    gdm_writer = session.get('gdm_writer')
    if gdm_writer:
        await gdm_writer.write_event(
            'checkpoint_saved',
            checkpoint_id=checkpoint_id,
            step=runner.step,
            label=label,
        )

    logger.info("Checkpoint saved: %s (step=%d, label=%r)", checkpoint_id, runner.step, label)
    return checkpoint_id


async def load_checkpoint(checkpoint_id: str, formulation) -> tuple:
    """Load a checkpoint from disk and deserialize the game state.

    Args:
        checkpoint_id: UUID hex string identifying the checkpoint.
        formulation:   A freshly loaded SZ_Formulation instance for this
                       game (used to discover the state class).

    Returns:
        (state, step_number) — the deserialized state and the step count
        at the time of the checkpoint.
    """
    file_path = await _get_checkpoint_file_path(checkpoint_id)
    data = await asyncio.to_thread(_read_json, file_path)

    # Discover the state class from the formulation by calling
    # initialize_problem() once.  The result is discarded immediately.
    state_class = type(formulation.initialize_problem())
    state = deserialize_state(data['state'], state_class)
    step  = data['step']

    logger.info("Checkpoint loaded: %s (step=%d)", checkpoint_id, step)
    return (state, step)


# ---------------------------------------------------------------------------
# Private I/O helpers
# ---------------------------------------------------------------------------

def _write_json(file_path: str, data: dict) -> None:
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)


def _read_json(file_path: str) -> dict:
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

@database_sync_to_async
def _get_checkpoint_file_path(checkpoint_id: str) -> str:
    from wsz6_play.models import Checkpoint
    cp = Checkpoint.objects.using('gdm').get(checkpoint_id=checkpoint_id)
    return cp.file_path


@database_sync_to_async
def _create_checkpoint_record(
    playthrough_id: str,
    checkpoint_id: str,
    file_path: str,
    step_number: int,
    label: str,
) -> None:
    try:
        from wsz6_play.models import Checkpoint, PlayThrough
        pt = PlayThrough.objects.using('gdm').get(playthrough_id=playthrough_id)
        Checkpoint.objects.using('gdm').create(
            checkpoint_id=checkpoint_id,
            playthrough=pt,
            file_path=file_path,
            step_number=step_number,
            label=label,
        )
    except Exception as exc:
        logger.warning("Could not create Checkpoint record: %s", exc)
