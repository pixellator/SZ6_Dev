"""
wsz6_shared/session_summary_schema.py

The shared contract for session summary data exchanged between
WSZ6-admin (UARD) and WSZ6-play (GDM).  Both components import
this file; neither imports the other's models directly.

Version history:
  v1  –  2026-02-18  Initial definition.
"""

SESSION_SUMMARY_SCHEMA_VERSION = '1'

# Template / documentation dict for a v1 session summary.
# All values shown are types or example values.
SESSION_SUMMARY_V1_SCHEMA = {
    'version':                    '1',         # str
    'session_key':                '<uuid>',    # str  (UUID4 hex with dashes)
    'game_slug':                  '<str>',     # str
    'owner_id':                   0,           # int  (WSZUser PK)
    'started_at':                 '<ISO8601>', # str
    'ended_at':                   '<ISO8601>', # str  (or null)
    'status':                     '<str>',     # 'completed' | 'interrupted' | 'paused'
    'playthrough_count':          0,           # int
    'completed_playthroughs':     0,           # int
    'interrupted_playthroughs':   0,           # int
    'players': [
        {
            'name':     '<str>',
            'role':     '<str>',
            'is_guest': True,
        }
    ],
    'gdm_path': '<str>',    # Relative path within GDM file system.
}


def validate_summary(data: dict) -> list[str]:
    """Return a list of error strings; empty list means valid."""
    errors = []
    required = ['version', 'session_key', 'game_slug', 'owner_id',
                 'started_at', 'status', 'playthrough_count', 'gdm_path']
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")
    if data.get('version') != SESSION_SUMMARY_SCHEMA_VERSION:
        errors.append(
            f"Unsupported schema version: {data.get('version')!r} "
            f"(expected {SESSION_SUMMARY_SCHEMA_VERSION!r})"
        )
    return errors
