"""
wsz6_admin/research/models.py

UARD-side models for the researcher panel.
These live in the default database (UARD), never in the GDM database.
"""

import uuid

from django.conf import settings
from django.db import models


class ResearchAnnotation(models.Model):
    """A researcher's personal annotation on a session, play-through, or log frame."""

    researcher      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='research_annotations',
    )
    # GDM entities referenced by key/ID (cross-DB — no FK possible).
    session_key     = models.UUIDField(db_index=True)
    playthrough_id  = models.UUIDField(null=True, blank=True, db_index=True)
    log_frame_index = models.IntegerField(null=True, blank=True)

    annotation  = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['session_key', 'playthrough_id', 'log_frame_index', 'created_at']

    def __str__(self):
        if self.log_frame_index is not None:
            level = f'frame {self.log_frame_index}'
        elif self.playthrough_id:
            level = f'playthrough {self.playthrough_id}'
        else:
            level = f'session {self.session_key}'
        return f"Annotation by {self.researcher} on {level}"


class ResearchAPIToken(models.Model):
    """A per-researcher Bearer token for external analytics tools."""

    researcher = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='research_api_token',
    )
    token      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used  = models.DateTimeField(null=True, blank=True)
    is_active  = models.BooleanField(default=True)

    def __str__(self):
        return f"APIToken for {self.researcher}"
