"""
wsz6_admin/sessions_log/models.py

Lightweight session summary records stored in the UARD database.
Detailed play-through logs live in the GDM (handled by wsz6_play).
"""

import uuid
from django.db import models
from django.conf import settings


class GameSession(models.Model):
    """One record per game session (not per play-through)."""

    STATUS_OPEN        = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_PAUSED      = 'paused'
    STATUS_COMPLETED   = 'completed'
    STATUS_INTERRUPTED = 'interrupted'

    STATUS_CHOICES = [
        (STATUS_OPEN,        'Open (lobby)'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_PAUSED,      'Paused'),
        (STATUS_COMPLETED,   'Completed'),
        (STATUS_INTERRUPTED, 'Interrupted'),
    ]

    session_key = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    owner       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_sessions',
    )
    game = models.ForeignKey(
        'games_catalog.Game',
        on_delete=models.PROTECT,
        related_name='sessions',
    )
    # Link to a previous session this one continues (optional).
    parent_session = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='continuation_sessions',
    )

    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at   = models.DateTimeField(null=True, blank=True)

    # Summary data pushed back from wsz6_play when session ends.
    summary_json = models.JSONField(default=dict)

    # Pointer into the GDM file system (relative path).
    gdm_path = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"Session {self.session_key} – {self.game.name} ({self.status})"
