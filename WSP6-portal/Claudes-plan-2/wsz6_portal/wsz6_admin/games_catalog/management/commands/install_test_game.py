"""
wsz6_admin/management/commands/install_test_game.py

Dev-only management command: install all SZ6 test games from the
Textual_SZ6 source tree into GAMES_REPO_ROOT and create (or update)
the corresponding Game records in the database.

Usage:
    python manage.py install_test_game
    python manage.py install_test_game --user admin --status published
"""

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
#   slug        – URL key used in the database and games_repo directory.
#                 The pff_loader will find the PFF by scanning the directory,
#                 so the filename does not need to match the slug exactly.
#   name        – human-readable display name
#   pff_file    – filename inside Textual_SZ6/
#   brief_desc  – shown on the game detail page
#   min_players – minimum players to start a session
#   max_players – maximum players allowed in a session
# ---------------------------------------------------------------------------

GAME_DEFS = [
    {
        'slug':        'tic-tac-toe',
        'name':        'Tic-Tac-Toe',
        'pff_file':    'Tic_Tac_Toe_SZ6.py',
        'brief_desc':  (
            "Tic-Tac-Toe is a two-player game on a 3×3 grid. "
            "X goes first. Get three in a row to win."
        ),
        'min_players': 2,
        'max_players': 27,
    },
    {
        'slug':        'tic-tac-toe-vis',
        'name':        'Tic-Tac-Toe (Visual)',
        'pff_file':    'Tic_Tac_Toe_SZ6_with_vis.py',
        'vis_file':    'Tic_Tac_Toe_WSZ6_VIS.py',
        'brief_desc':  (
            "Tic-Tac-Toe with SVG board visualization. "
            "Identical rules to the standard version, but the board is "
            "rendered as a graphic instead of ASCII text. "
            "Demonstrates the WSZ6 M1 (basic visualization) feature."
        ),
        'min_players': 2,
        'max_players': 27,
    },
    {
        'slug':        'guess-my-age',
        'name':        'Guess My Age',
        'pff_file':    'Guess_My_Age_SZ6.py',
        'brief_desc':  (
            "A simple single-player game that demonstrates random game "
            "instances and a parameterized operator. The computer picks "
            "a secret age between 14 and 21; the player guesses until correct."
        ),
        'min_players': 1,
        'max_players': 1,
    },
    {
        'slug':        'missionaries',
        'name':        'Missionaries and Cannibals',
        'pff_file':    'Missionaries_SZ6.py',
        'brief_desc':  (
            'The "Missionaries and Cannibals" problem is a classic puzzle: '
            "three missionaries and three cannibals must cross a river using "
            "a boat that holds at most three people. Missionaries must never "
            "be outnumbered by cannibals on either bank or in the boat."
        ),
        'min_players': 1,
        'max_players': 1,
    },
    {
        'slug':        'rock-paper-scissors',
        'name':        'Rock-Paper-Scissors',
        'pff_file':    'Rock_Paper_Scissors_SZ6.py',
        'brief_desc':  (
            "A two-player Rock-Paper-Scissors match over 3 rounds. "
            "Each round both players simultaneously choose Rock, Paper, or "
            "Scissors. Rock beats Scissors, Scissors beats Paper, Paper beats "
            "Rock. Highest cumulative score after all rounds wins the match."
        ),
        'min_players': 2,
        'max_players': 2,
    },
    {
        'slug':        'remote-llm-test',
        'name':        'Remote LLM Test Game',
        'pff_file':    'Remote_LLM_Test_Game_SZ6.py',
        'brief_desc':  (
            "A minimal test game that sends free-text prompts to a remote "
            "Gemini LLM and displays its response as a transition message. "
            "The player may send multiple prompts before choosing to finish. "
            "Requires the GEMINI_API_KEY environment variable and the "
            "google-genai Python package."
        ),
        'min_players': 1,
        'max_players': 1,
    },
    {
        'slug':        'trivial-writing-game',
        'name':        'Trivial Writing Game',
        'pff_file':    'Trivial_Writing_Game_SZ6.py',
        'brief_desc':  (
            "A minimal single-player writing exercise. The player submits "
            "a text document; when done, the engine reports word-frequency "
            "counts of the document. Demonstrates the file_edit operator "
            "parameter type."
        ),
        'min_players': 1,
        'max_players': 1,
    },
    {
        'slug':        'show-mt-rainier',
        'name':        'Mt. Rainier Views',
        'pff_file':    'Show_Mt_Rainier_SZ6.py',
        'vis_file':    'Show_Mt_Rainier_WSZ6_VIS.py',
        'images_dir':  'Show_Mt_Rainier_images',
        # Sources live in Vis-Features-Dev rather than the default Textual_SZ6.
        # Path is relative to BASE_DIR.parent (i.e. Claudes-plan-2/).
        'source_dir':  'Vis-Features-Dev/game_sources',
        'brief_desc':  (
            "Browse five scenic SVG illustrations of Mt. Rainier National "
            "Park — the summit, Paradise Meadows, Reflection Lakes, Carbon "
            "Glacier, and the Skyline Trail. Each scene comes with a "
            "descriptive caption. The goal is to view all five scenes. "
            "Demonstrates the WSZ6 M2 image-resource feature."
        ),
        'min_players': 1,
        'max_players': 1,
    },
    {
        'slug':        'click-the-word',
        'name':        "Cliquez sur l'image",
        'pff_file':    'Click_Word_SZ6.py',
        'vis_file':    'Click_Word_WSZ6_VIS.py',
        # Sources live in Vis-Features-Dev/game_sources/.
        'source_dir':  'Vis-Features-Dev/game_sources',
        'brief_desc':  (
            "A single-player French vocabulary game. A stylised room scene "
            "is displayed alongside a French word; click on the matching "
            "object in the scene. Six objects: apple, window, table, chair, "
            "cup, and book. Incorrect clicks are counted. "
            "Demonstrates the WSZ6 M3 Tier-2 canvas hit-testing feature."
        ),
        'min_players': 1,
        'max_players': 1,
    },
    {
        'slug':        'pixel-uw-aerial',
        'name':        'Pixel Values with Old UW Aerial Image',
        'pff_file':    'Pixel_Probe_SZ6.py',
        'vis_file':    'Pixel_Probe_WSZ6_VIS.py',
        'images_dir':  'UW_Aerial_images',
        'source_dir':  'Vis-Features-Dev/game_sources',
        'brief_desc':  (
            'Click on an aerial photograph of the University of Washington '
            'to read the pixel values at the clicked point. '
            'The top half of the image reports RGB values; the bottom half '
            'reports HSV values. '
            'Demonstrates Tier-2 canvas regions on a raster JPEG with '
            'dynamic coordinate capture and server-side Pillow image access.'
        ),
        'min_players': 1,
        'max_players': 1,
    },
    {
        'slug':        'occluedo',
        'name':        'OCCLUEdo: An Occluded Game of Clue',
        'pff_file':    'OCCLUEdo_SZ6.py',
        'vis_file':    'OCCLUEdo_WSZ6_VIS.py',
        'images_dir':  'OCCLUEdo_images',
        'source_dir':  'Vis-Features-Dev/game_sources',
        'brief_desc':  (
            'A simplified online Clue/Cluedo for 2-6 players plus observers. '
            'Players move between rooms, make suggestions about the murder, '
            'and try to identify the murderer, weapon, and room before anyone else. '
            'Secret cards are dealt at the start; players show cards to disprove '
            "each other's suggestions. "
            'Demonstrates Tier-1 SVG interaction with role-based multiplayer.'
        ),
        'min_players': 2,
        'max_players': 7,
    },
]


class Command(BaseCommand):
    help = "Install all SZ6 test games from Textual_SZ6 into GAMES_REPO_ROOT."

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
        # Locate source directory
        # ------------------------------------------------------------------
        # BASE_DIR is wsz6_portal/; Textual_SZ6 is at SZ6_Dev/Textual_SZ6/
        textual_dir = settings.BASE_DIR.parent.parent.parent / 'Textual_SZ6'
        if not textual_dir.is_dir():
            raise CommandError(
                f"Textual_SZ6 source directory not found at {textual_dir}. "
                "Adjust the path in install_test_game.py if your layout differs."
            )

        src_base = textual_dir / 'soluzion6_02.py'
        if not src_base.exists():
            raise CommandError(f"Base module not found: {src_base}")

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
        installed = 0
        skipped   = 0

        # repo_root is Claudes-plan-2/ (one level above wsz6_portal/).
        repo_root = settings.BASE_DIR.parent

        for gdef in GAME_DEFS:
            # Each game may override the source directory via 'source_dir'
            # (relative to repo_root).  Falls back to the default textual_dir.
            if 'source_dir' in gdef:
                src_dir = repo_root / gdef['source_dir']
            else:
                src_dir = textual_dir
            ok = self._install_game(
                gdef, src_dir, src_base, games_repo, owner, status, Game
            )
            if ok:
                installed += 1
            else:
                skipped += 1

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

    def _install_game(self, gdef, src_dir, src_base, games_repo,
                      owner, status, Game):
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

        # Copy PFF and base module into the game's repo directory.
        dest_dir = games_repo / slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_pff,  dest_dir / pff_file)
        shutil.copy2(src_base, dest_dir / src_base.name)

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
        # Source: <src_dir>/<images_dir>/
        # Destination: <dest_dir>/<images_dir>/   (preserves the folder name
        #   so asset URLs remain stable across re-installs).
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
