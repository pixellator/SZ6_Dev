"""
wsz6_play/persistence/session_sync.py

Updates the UARD GameSession record when a session ends or changes status.

Phase-2 implementation:
    Because WSZ6-admin and WSZ6-play are in the same Django process, we
    import GameSession directly rather than making an HTTP call.  This is
    wrapped in asyncio.to_thread() so the async game consumer is never
    blocked by a database write.

Phase-7 upgrade path:
    Replace the direct ORM calls with HTTP POSTs/PATCHes to the
    /internal/v1/ API (already stubbed).  The async interface stays the same.
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def push_session_ended(session_key: str, summary: dict) -> None:
    """Mark the UARD GameSession as completed and store the summary JSON."""
    await asyncio.to_thread(_update_session_sync, session_key, summary)


async def push_session_status(session_key: str, status: str) -> None:
    """Update the UARD GameSession status field."""
    await asyncio.to_thread(_update_status_sync, session_key, status)


# ---------------------------------------------------------------------------
# Synchronous helpers (run in thread pool)
# ---------------------------------------------------------------------------

def _update_session_sync(session_key: str, summary: dict) -> None:
    try:
        from wsz6_admin.sessions_log.models import GameSession
        gs = GameSession.objects.filter(session_key=session_key).first()
        if gs is None:
            logger.warning("session_sync: GameSession %s not found", session_key)
            return
        gs.status       = GameSession.STATUS_COMPLETED
        gs.ended_at     = datetime.now(timezone.utc)
        gs.summary_json = summary
        gs.gdm_path     = summary.get('gdm_path', '')
        gs.save(update_fields=['status', 'ended_at', 'summary_json', 'gdm_path'])
        logger.info("session_sync: updated %s → completed", session_key)
    except Exception as exc:
        logger.warning("session_sync: failed to update %s: %s", session_key, exc)


def _update_status_sync(session_key: str, status: str) -> None:
    try:
        from wsz6_admin.sessions_log.models import GameSession
        gs = GameSession.objects.filter(session_key=session_key).first()
        if gs:
            gs.status = status
            gs.save(update_fields=['status'])
    except Exception as exc:
        logger.warning("session_sync: failed to update status for %s: %s", session_key, exc)
