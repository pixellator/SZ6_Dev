"""
wsz6_admin/management/commands/install_test_game.py

Dev-only management command: install all SZ6 test games from the canonical
SZ6_Dev/game_sources/ source tree into GAMES_REPO_ROOT and create (or update)
the corresponding Game records in the database.

Each game has its own subdirectory under game_sources/ (e.g. game_sources/tic_tac_toe/).
The shared SOLUZION6 base library (soluzion6_02.py) is NOT copied into each game
directory; instead, pff_loader adds settings.SOLUZION_LIB_DIR (Textual_SZ6/) to
sys.path so all games share the single authoritative copy.

A metadata.json is written to each installed game directory for self-documentation.

Usage:
    python manage.py install_test_game
    python manage.py install_test_game --user admin --status published
"""

import datetime
import json
import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


# ---------------------------------------------------------------------------
# Game definitions
# ---------------------------------------------------------------------------
# Each entry describes one SZ6 game to install.
#
#   slug          – URL key used in the database and games_repo directory.
#   name          – human-readable display name
#   source_subdir – subdirectory under SZ6_Dev/game_sources/ containing the sources
#   pff_file      – PFF filename inside source_subdir/
#   vis_file      – (optional) vis module filename inside source_subdir/
#   images_dir    – (optional) images subdirectory name inside source_subdir/
#   brief_desc    – shown on the game detail page
#   min_players   – minimum players to start a session
#   max_players   – maximum players allowed in a session
# ---------------------------------------------------------------------------

GAME_DEFS = [
    {
        'slug':          'tic-tac-toe',
        'name':          'Tic-Tac-Toe',
        'source_subdir': 'tic_tac_toe',
        'pff_file':      'Tic_Tac_Toe_SZ6.py',
        'vis_file':      'Tic_Tac_Toe_WSZ6_VIS.py',
        'brief_desc':    (
            "Tic-Tac-Toe is a two-player game on a 3×3 grid with SVG visualization. "
            "X goes first. Get three in a row to win."
        ),
        'min_players':   2,
        'max_players':   27,
    },
    {
        'slug':          'missionaries',
        'name':          'Missionaries and Cannibals',
        'source_subdir': 'missionaries',
        'pff_file':      'Missionaries_SZ6.py',
        'brief_desc':    (
            'The "Missionaries and Cannibals" problem is a classic puzzle: '
            "three missionaries and three cannibals must cross a river using "
            "a boat that holds at most three people. Missionaries must never "
            "be outnumbered by cannibals on either bank or in the boat."
        ),
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'guess-my-age',
        'name':          'Guess My Age',
        'source_subdir': 'guess_my_age',
        'pff_file':      'Guess_My_Age_SZ6.py',
        'brief_desc':    (
            "A simple single-player game that demonstrates random game "
            "instances and a parameterized operator. The computer picks "
            "a secret age between 14 and 21; the player guesses until correct."
        ),
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'rock-paper-scissors',
        'name':          'Rock-Paper-Scissors',
        'source_subdir': 'rock_paper_scissors',
        'pff_file':      'Rock_Paper_Scissors_SZ6.py',
        'brief_desc':    (
            "A two-player Rock-Paper-Scissors match over 3 rounds. "
            "Each round both players simultaneously choose Rock, Paper, or "
            "Scissors. Rock beats Scissors, Scissors beats Paper, Paper beats "
            "Rock. Highest cumulative score after all rounds wins the match."
        ),
        'min_players':   2,
        'max_players':   2,
    },
    {
        'slug':          'remote-llm-test',
        'name':          'Remote LLM Test Game',
        'source_subdir': 'remote_llm_test',
        'pff_file':      'Remote_LLM_Test_Game_SZ6.py',
        'brief_desc':    (
            "A minimal test game that sends free-text prompts to a remote "
            "Gemini LLM and displays its response as a transition message. "
            "The player may send multiple prompts before choosing to finish. "
            "Requires the GEMINI_API_KEY environment variable and the "
            "google-genai Python package."
        ),
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'trivial-writing-game',
        'name':          'Trivial Writing Game',
        'source_subdir': 'trivial_writing_game',
        'pff_file':      'Trivial_Writing_Game_SZ6.py',
        'brief_desc':    (
            "A minimal single-player writing exercise. The player submits "
            "a text document; when done, the engine reports word-frequency "
            "counts of the document. Demonstrates the file_edit operator "
            "parameter type."
        ),
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'show-mt-rainier',
        'name':          'Mt. Rainier Views',
        'source_subdir': 'show_mt_rainier',
        'pff_file':      'Show_Mt_Rainier_SZ6.py',
        'vis_file':      'Show_Mt_Rainier_WSZ6_VIS.py',
        'images_dir':    'Show_Mt_Rainier_images',
        'brief_desc':    (
            "Browse five scenic SVG illustrations of Mt. Rainier National "
            "Park — the summit, Paradise Meadows, Reflection Lakes, Carbon "
            "Glacier, and the Skyline Trail. Each scene comes with a "
            "descriptive caption. The goal is to view all five scenes. "
            "Demonstrates the WSZ6 M2 image-resource feature."
        ),
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'click-the-word',
        'name':          "Cliquez sur l'image",
        'source_subdir': 'click_the_word',
        'pff_file':      'Click_Word_SZ6.py',
        'vis_file':      'Click_Word_WSZ6_VIS.py',
        'brief_desc':    (
            "A single-player French vocabulary game. A stylised room scene "
            "is displayed alongside a French word; click on the matching "
            "object in the scene. Six objects: apple, window, table, chair, "
            "cup, and book. Incorrect clicks are counted. "
            "Demonstrates the WSZ6 M3 Tier-2 canvas hit-testing feature."
        ),
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'pixel-uw-aerial',
        'name':          'Pixel Values with Old UW Aerial Image',
        'source_subdir': 'pixel_uw_aerial',
        'pff_file':      'Pixel_Probe_SZ6.py',
        'vis_file':      'Pixel_Probe_WSZ6_VIS.py',
        'images_dir':    'UW_Aerial_images',
        'brief_desc':    (
            'Click on an aerial photograph of the University of Washington '
            'to read the pixel values at the clicked point. '
            'The top half of the image reports RGB values; the bottom half '
            'reports HSV values. '
            'Demonstrates Tier-2 canvas regions on a raster JPEG with '
            'dynamic coordinate capture and server-side Pillow image access.'
        ),
        'min_players':   1,
        'max_players':   1,
    },
    {
        'slug':          'occluedo',
        'name':          'OCCLUEdo: An Occluded Game of Clue',
        'source_subdir': 'occluedo',
        'pff_file':      'OCCLUEdo_SZ6.py',
        'vis_file':      'OCCLUEdo_WSZ6_VIS.py',
        'images_dir':    'OCCLUEdo_images',
        'brief_desc':    (
            'A simplified online Clue/Cluedo for 2-6 players plus observers. '
            'Players move between rooms, make suggestions about the murder, '
            'and try to identify the murderer, weapon, and room before anyone else. '
            'Secret cards are dealt at the start; players show cards to disprove '
            "each other's suggestions. "
            'Demonstrates Tier-1 SVG interaction with role-based multiplayer.'
        ),
        'min_players':   2,
        'max_players':   7,
    },
]


class Command(BaseCommand):
    help = (
        "Install all SZ6 test games from SZ6_Dev/game_sources/ into GAMES_REPO_ROOT. "
        "Removes the obsolete tic-tac-toe-vis catalog entry."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            default=None,
            help='Username of the installing admin (defaults to first superuser)',
        )
        parser.add_argument(
            '--status',
            default='published',
            choices=['dev', 'beta', 'published'],
            help='Status applied to newly created game records (default: published)',
        )

    def handle(self, *args, **options):
        status = options['status']

        # ------------------------------------------------------------------
        # Locate the canonical game sources root
        # ------------------------------------------------------------------
        # BASE_DIR is wsz6_portal/; game_sources is at SZ6_Dev/game_sources/
        game_sources = settings.BASE_DIR.parent.parent.parent / 'game_sources'
        if not game_sources.is_dir():
            raise CommandError(
                f"game_sources directory not found at {game_sources}. "
                "Run Step 1 of Games_File_System_Refactoring.md to create it."
            )

        # ------------------------------------------------------------------
        # Resolve owner
        # ------------------------------------------------------------------
        User = get_user_model()
        owner = None
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
        # Install each game
        # ------------------------------------------------------------------
        from wsz6_admin.games_catalog.models import Game

        games_repo = Path(settings.GAMES_REPO_ROOT)
        installed  = 0
        skipped    = 0

        for gdef in GAME_DEFS:
            src_dir = game_sources / gdef['source_subdir']
            ok = self._install_game(gdef, src_dir, games_repo, owner, status, Game)
            if ok:
                installed += 1
            else:
                skipped += 1

        # ------------------------------------------------------------------
        # Remove the obsolete tic-tac-toe-vis catalog entry (now collapsed
        # into tic-tac-toe via auto-discovery of the vis module).
        # Any referencing GameSession records (stale dev sessions) are deleted
        # first to satisfy the PROTECTED foreign key constraint.
        # ------------------------------------------------------------------
        old_game_qs = Game.objects.filter(slug='tic-tac-toe-vis')
        if old_game_qs.exists():
            old_game = old_game_qs.first()
            session_count = old_game.sessions.count()
            if session_count:
                old_game.sessions.all().delete()
                self.stdout.write(self.style.WARNING(
                    f"  DEL   Removed {session_count} stale session(s) for 'tic-tac-toe-vis'."
                ))
            old_game.delete()
            self.stdout.write(self.style.SUCCESS(
                "  DEL   Removed obsolete 'tic-tac-toe-vis' catalog entry."
            ))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done: {installed} game(s) installed, {skipped} skipped."
        ))
        self.stdout.write("Next steps:")
        self.stdout.write("  1. Visit http://localhost:8000/games/ to see all games.")
        self.stdout.write("  2. Click a game and then 'New Session' to start a lobby.")

    # ------------------------------------------------------------------
    # Per-game helper
    # ------------------------------------------------------------------

    def _install_game(self, gdef, src_dir, games_repo, owner, status, Game):
        """Copy files and upsert the Game record. Returns True on success."""
        slug     = gdef['slug']
        name     = gdef['name']
        pff_file = gdef['pff_file']

        src_pff = src_dir / pff_file
        if not src_pff.exists():
            self.stdout.write(self.style.WARNING(
                f"  SKIP  '{name}': PFF not found at {src_pff}"
            ))
            return False

        # Create destination directory and copy the PFF.
        # Note: soluzion6_02.py is NOT copied here; pff_loader adds
        # settings.SOLUZION_LIB_DIR (Textual_SZ6/) to sys.path instead.
        dest_dir = games_repo / slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_pff, dest_dir / pff_file)

        # Copy optional visualization module if specified.
        vis_file = gdef.get('vis_file')
        if vis_file:
            src_vis = src_dir / vis_file
            if src_vis.exists():
                shutil.copy2(src_vis, dest_dir / vis_file)
            else:
                self.stdout.write(self.style.WARNING(
                    f"  WARN  vis file not found: {src_vis}"
                ))

        # Copy optional images directory if specified.
        images_dir = gdef.get('images_dir')
        if images_dir:
            src_imgs = src_dir / images_dir
            dst_imgs = dest_dir / images_dir
            if src_imgs.is_dir():
                if dst_imgs.exists():
                    shutil.rmtree(dst_imgs)
                shutil.copytree(src_imgs, dst_imgs)
            else:
                self.stdout.write(self.style.WARNING(
                    f"  WARN  images_dir not found: {src_imgs}"
                ))

        # Write metadata.json for self-documentation and future bulk-install use.
        metadata = {
            'slug':         slug,
            'name':         name,
            'version':      '1.0',
            'min_players':  gdef['min_players'],
            'max_players':  gdef['max_players'],
            'pff_file':     pff_file,
            'vis_file':     vis_file or '',
            'images_dir':   gdef.get('images_dir', ''),
            'installed_at': datetime.datetime.utcnow().isoformat() + 'Z',
        }
        (dest_dir / 'metadata.json').write_text(
            json.dumps(metadata, indent=2), encoding='utf-8'
        )

        # Create or update the Game record.
        game, created = Game.objects.get_or_create(
            slug=slug,
            defaults={
                'name':          name,
                'brief_desc':    gdef['brief_desc'],
                'status':        status,
                'min_players':   gdef['min_players'],
                'max_players':   gdef['max_players'],
                'pff_path':      str(dest_dir),
                'metadata_json': {
                    'name':        name,
                    'version':     '1.0',
                    'min_players': gdef['min_players'],
                    'max_players': gdef['max_players'],
                },
                'owner':         owner,
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS(
                f"  OK    '{name}' created  (slug='{slug}', status='{status}')"
            ))
        else:
            game.pff_path = str(dest_dir)
            if owner:
                game.owner = owner
            game.save(update_fields=['pff_path', 'owner'])
            self.stdout.write(self.style.WARNING(
                f"  UPD   '{name}' already exists — pff_path updated."
            ))

        return True
