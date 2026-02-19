"""
wsz6_admin/accounts/models.py

Custom user model for WSZ6-portal.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class WSZUser(AbstractUser):
    """Extended user with WSZ6-specific fields."""

    # --- User type ---
    ADMIN_GENERAL   = 'admin_general'
    ADMIN_ACCOUNTS  = 'admin_accounts'
    ADMIN_GAMES     = 'admin_games'
    ADMIN_RESEARCH  = 'admin_research'
    SESSION_OWNER   = 'session_owner'
    GAME_OWNER      = 'game_owner'
    PLAYER          = 'player'

    USER_TYPE_CHOICES = [
        (ADMIN_GENERAL,  'General Admin'),
        (ADMIN_ACCOUNTS, 'User-Account Admin'),
        (ADMIN_GAMES,    'Game Admin'),
        (ADMIN_RESEARCH, 'Research Admin'),
        (SESSION_OWNER,  'Game-Session Owner'),
        (GAME_OWNER,     'Individual Game Owner'),
        (PLAYER,         'Individual Player'),
    ]

    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default=SESSION_OWNER,
    )

    # --- Game access level ---
    ACCESS_PUBLISHED = 'published'
    ACCESS_BETA      = 'beta'
    ACCESS_ALL       = 'all'
    ACCESS_CUSTOM    = 'custom'

    GAME_ACCESS_CHOICES = [
        (ACCESS_PUBLISHED, 'Published games only'),
        (ACCESS_BETA,      'Published and Beta games'),
        (ACCESS_ALL,       'All games'),
        (ACCESS_CUSTOM,    'Custom list'),
    ]

    game_access_level = models.CharField(
        max_length=20,
        choices=GAME_ACCESS_CHOICES,
        default=ACCESS_PUBLISHED,
    )

    # Custom game list (used when game_access_level == 'custom').
    # Forward reference resolved via string; avoids circular import.
    allowed_games = models.ManyToManyField(
        'games_catalog.Game',
        blank=True,
        related_name='explicitly_allowed_users',
    )

    class Meta:
        verbose_name = 'WSZ User'
        verbose_name_plural = 'WSZ Users'

    # --- Convenience helpers ---

    def is_any_admin(self):
        return self.user_type in (
            self.ADMIN_GENERAL,
            self.ADMIN_ACCOUNTS,
            self.ADMIN_GAMES,
            self.ADMIN_RESEARCH,
        )

    def can_install_games(self):
        return self.user_type in (self.ADMIN_GENERAL, self.ADMIN_GAMES)

    def can_access_research(self):
        return self.user_type in (self.ADMIN_GENERAL, self.ADMIN_RESEARCH)

    def can_start_sessions(self):
        return self.user_type in (
            self.ADMIN_GENERAL,
            self.SESSION_OWNER,
            self.GAME_OWNER,
        )
