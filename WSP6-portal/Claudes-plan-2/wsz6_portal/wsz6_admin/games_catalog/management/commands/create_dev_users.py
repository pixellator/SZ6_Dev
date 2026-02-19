"""
wsz6_admin/games_catalog/management/commands/create_dev_users.py

Dev-only command: create a small set of test users covering every
user_type so all portal features can be exercised quickly.

Usage:
    python manage.py create_dev_users
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

DEFAULT_PASSWORD = 'pass1234'

USERS = [
    # (username, email, user_type, is_staff, is_superuser)
    ('admin',    'admin@localhost',   'admin_general', True,  True),
    ('gameadm',  'gameadm@localhost', 'admin_games',   True,  False),
    ('owner1',   'owner1@localhost',  'session_owner', False, False),
    ('owner2',   'owner2@localhost',  'session_owner', False, False),
    ('player1',  'player1@localhost', 'player',        False, False),
    ('player2',  'player2@localhost', 'player',        False, False),
]


class Command(BaseCommand):
    help = (
        "Create development/test users.  "
        f"All users get password '{DEFAULT_PASSWORD}'."
    )

    def handle(self, *args, **options):
        User = get_user_model()

        for username, email, user_type, is_staff, is_superuser in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email':        email,
                    'user_type':    user_type,
                    'is_staff':     is_staff,
                    'is_superuser': is_superuser,
                    'game_access_level': 'all',
                },
            )
            if created:
                user.set_password(DEFAULT_PASSWORD)
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f"  Created {username} ({user_type})"
                ))
            else:
                self.stdout.write(f"  {username} already exists — skipped.")

        self.stdout.write("")
        self.stdout.write(f"Password for all new users: {DEFAULT_PASSWORD!r}")
        self.stdout.write("Log in at http://localhost:8000/accounts/login/")
