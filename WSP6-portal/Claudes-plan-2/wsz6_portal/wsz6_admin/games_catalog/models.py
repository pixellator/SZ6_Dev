"""
wsz6_admin/games_catalog/models.py

Game catalogue entries stored in the UARD database.
"""

import uuid
from django.db import models
from django.conf import settings


class Game(models.Model):
    """Represents a SOLUZION6 game installed on the portal."""

    STATUS_DEV        = 'dev'
    STATUS_BETA       = 'beta'
    STATUS_PUBLISHED  = 'published'
    STATUS_DEPRECATED = 'deprecated'

    STATUS_CHOICES = [
        (STATUS_DEV,        'Development'),
        (STATUS_BETA,       'Beta'),
        (STATUS_PUBLISHED,  'Published'),
        (STATUS_DEPRECATED, 'Deprecated'),
    ]

    name          = models.CharField(max_length=200, unique=True)
    slug          = models.SlugField(max_length=100, unique=True)
    brief_desc    = models.TextField(blank=True)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DEV)
    min_players   = models.PositiveIntegerField(default=1)
    max_players   = models.PositiveIntegerField(default=10)

    # Path within GAMES_REPO_ROOT where the PFF and assets live.
    pff_path      = models.CharField(max_length=500, blank=True)

    # JSON dump of the SZ_Metadata from the PFF.
    metadata_json = models.JSONField(default=dict)

    # Timestamps
    installed_at  = models.DateTimeField(auto_now_add=True)
    beta_at       = models.DateTimeField(null=True, blank=True)
    published_at  = models.DateTimeField(null=True, blank=True)
    updated_at    = models.DateTimeField(auto_now=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='owned_games',
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.status})"
