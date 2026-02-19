"""
wsz6_play/models.py  –  GDM-side database models.

These models live in the 'gdm' database (see DATABASE_ROUTERS).
Full implementation deferred to Phase 2.
"""

import uuid
from django.db import models


class PlayThrough(models.Model):
    """One play-through within a game session."""

    playthrough_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Session key mirrors the GameSession UUID in the UARD.
    session_key    = models.UUIDField(db_index=True)
    game_slug      = models.CharField(max_length=100)
    started_at     = models.DateTimeField(auto_now_add=True)
    ended_at       = models.DateTimeField(null=True, blank=True)
    outcome        = models.CharField(
        max_length=20,
        choices=[('completed','Completed'), ('interrupted','Interrupted'),
                 ('cancelled','Cancelled')],
        blank=True,
    )
    log_path       = models.CharField(max_length=500)   # Path to .jsonl log file.
    step_count     = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'wsz6_play'
        ordering  = ['-started_at']

    def __str__(self):
        return f"PlayThrough {self.playthrough_id} ({self.game_slug})"


class Checkpoint(models.Model):
    """A saved game state from which play can be resumed."""

    checkpoint_id  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    playthrough    = models.ForeignKey(PlayThrough, on_delete=models.CASCADE,
                                       related_name='checkpoints')
    created_at     = models.DateTimeField(auto_now_add=True)
    label          = models.CharField(max_length=200, blank=True)
    file_path      = models.CharField(max_length=500)   # Path to checkpoint JSON file.
    step_number    = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'wsz6_play'
        ordering  = ['-created_at']
