"""
wsz6_admin/management/commands/install_test_game.py

Dev-only management command: copy the Tic-Tac-Toe SZ6 formulation from
the Textual_SZ6 source tree into GAMES_REPO_ROOT and create the
corresponding Game record in the UARD database.

Usage:
    python manage.py install_test_game
    python manage.py install_test_game --slug tic-tac-toe --user admin
"""

import os
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify


class Command(BaseCommand):
    help = "Install the Tic-Tac-Toe SZ6 game for development/testing."

    def add_arguments(self, parser):
        parser.add_argument(
            '--slug',
            default='tic-tac-toe',
            help='Game slug (default: tic-tac-toe)',
        )
        parser.add_argument(
            '--name',
            default='Tic-Tac-Toe',
            help='Game name (default: Tic-Tac-Toe)',
        )
        parser.add_argument(
            '--user',
            default=None,
            help='Username of the installing admin (defaults to first superuser)',
        )
        parser.add_argument(
            '--status',
            default='published',
            choices=['dev', 'beta', 'published'],
            help='Game status (default: published)',
        )

    def handle(self, *args, **options):
        slug   = options['slug']
        name   = options['name']
        status = options['status']

        # ------------------------------------------------------------------
        # Locate source files
        # ------------------------------------------------------------------
        # BASE_DIR is wsz6_portal/; Textual_SZ6 is at SZ6_Dev/Textual_SZ6/
        textual_dir = settings.BASE_DIR.parent.parent.parent / 'Textual_SZ6'
        if not textual_dir.is_dir():
            raise CommandError(
                f"Textual_SZ6 source directory not found at {textual_dir}. "
                "Adjust the path in install_test_game.py if your layout differs."
            )

        src_pff      = textual_dir / 'Tic_Tac_Toe_SZ6.py'
        src_base     = textual_dir / 'soluzion6_02.py'

        if not src_pff.exists():
            raise CommandError(f"PFF not found: {src_pff}")
        if not src_base.exists():
            raise CommandError(f"Base module not found: {src_base}")

        # ------------------------------------------------------------------
        # Copy to games repo
        # ------------------------------------------------------------------
        games_repo = Path(settings.GAMES_REPO_ROOT)
        dest_dir   = games_repo / slug
        dest_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(src_pff,  dest_dir / src_pff.name)
        shutil.copy2(src_base, dest_dir / src_base.name)
        self.stdout.write(f"  Copied PFF to {dest_dir}/")

        # ------------------------------------------------------------------
        # Resolve owner
        # ------------------------------------------------------------------
        User = get_user_model()
        if options['user']:
            try:
                owner = User.objects.get(username=options['user'])
            except User.DoesNotExist:
                raise CommandError(f"User '{options['user']}' not found.")
        else:
            owner = User.objects.filter(is_superuser=True).first()
            if owner is None:
                self.stdout.write(self.style.WARNING(
                    "No superuser found; Game.owner will be NULL."
                ))

        # ------------------------------------------------------------------
        # Create or update the Game record
        # ------------------------------------------------------------------
        from wsz6_admin.games_catalog.models import Game

        game, created = Game.objects.get_or_create(
            slug=slug,
            defaults={
                'name':        name,
                'brief_desc':  (
                    "Tic-Tac-Toe is a two-player game on a 3×3 grid. "
                    "X goes first. Get three in a row to win."
                ),
                'status':      status,
                'min_players': 2,
                'max_players': 27,
                'pff_path':    str(dest_dir),
                'metadata_json': {
                    'name':        name,
                    'version':     '1.0',
                    'desc':        'Tic-Tac-Toe SZ6 formulation.',
                    'min_players': 2,
                    'max_players': 27,
                },
                'owner':       owner,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(
                f"Game '{name}' created (slug='{slug}', status='{status}')."
            ))
        else:
            # Update the path in case the repo moved.
            game.pff_path = str(dest_dir)
            if owner:
                game.owner = owner
            game.save(update_fields=['pff_path', 'owner'])
            self.stdout.write(self.style.WARNING(
                f"Game '{slug}' already exists — updated pff_path."
            ))

        self.stdout.write("")
        self.stdout.write("Next steps:")
        self.stdout.write(f"  1. Visit http://localhost:8000/games/{slug}/ to see the game.")
        self.stdout.write(f"  2. Click 'New Session' to start a lobby.")
        self.stdout.write(f"  3. Open a second browser window (different user) and join.")
