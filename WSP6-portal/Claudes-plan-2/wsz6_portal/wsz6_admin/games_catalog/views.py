"""
wsz6_admin/games_catalog/views.py

Game catalogue: list, detail, installation, and status editing.
"""

import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import GameEditForm, GameInstallForm
from .installer import InstallError, validate_and_extract, validate_pff
from .models import Game

logger = logging.getLogger(__name__)


def _can_install(user):
    return user.is_authenticated and user.can_install_games()


install_required = user_passes_test(_can_install, login_url='/accounts/login/')


# ---------------------------------------------------------------------------
# Public / session-owner views
# ---------------------------------------------------------------------------

@login_required
def game_list(request):
    """List of games the current user can access."""
    user = request.user
    q    = request.GET.get('q', '').strip()

    if user.is_any_admin():
        games = Game.objects.all()
    elif user.game_access_level == 'all':
        games = Game.objects.all()
    elif user.game_access_level == 'beta':
        games = Game.objects.filter(status__in=[Game.STATUS_PUBLISHED, Game.STATUS_BETA])
    elif user.game_access_level == 'custom':
        games = user.allowed_games.all()
    else:
        games = Game.objects.filter(status=Game.STATUS_PUBLISHED)

    if q:
        games = games.filter(
            Q(name__icontains=q) | Q(brief_desc__icontains=q)
        )

    games = games.annotate(session_count=Count('sessions')).order_by('name')
    return render(request, 'games_catalog/list.html', {
        'games': games, 'q': q,
        'can_install': user.can_install_games(),
    })


@login_required
def game_detail(request, slug):
    """Game detail page with stats and admin controls."""
    game = get_object_or_404(Game, slug=slug)
    user = request.user

    if request.method == 'POST' and user.can_install_games():
        form = GameEditForm(request.POST, instance=game)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{game.name}" updated.')
            return redirect('games_catalog:detail', slug=game.slug)
    else:
        form = GameEditForm(instance=game) if user.can_install_games() else None

    sessions = game.sessions.order_by('-started_at')[:10]
    return render(request, 'games_catalog/detail.html', {
        'game': game,
        'form': form,
        'sessions': sessions,
        'can_install': user.can_install_games(),
    })


# ---------------------------------------------------------------------------
# Game installation (game admins only)
# ---------------------------------------------------------------------------

@install_required
def game_install(request):
    """Upload a ZIP, validate it, extract, sandbox-validate the PFF, create Game record."""
    if request.method == 'POST':
        form = GameInstallForm(request.POST, request.FILES)
        if form.is_valid():
            slug     = form.cleaned_data['slug']
            zip_file = request.FILES['zip_file']

            # 1. Extract ZIP to games repo.
            try:
                game_dir = validate_and_extract(zip_file, slug)
            except InstallError as e:
                messages.error(request, f'ZIP error: {e}')
                return render(request, 'games_catalog/install.html', {'form': form})

            # 2. Sandbox-validate the PFF and extract metadata.
            try:
                meta = validate_pff(game_dir)
            except InstallError as e:
                messages.error(request, f'PFF validation error: {e}')
                return render(request, 'games_catalog/install.html', {'form': form})

            # 3. Create the Game record.
            game = Game.objects.create(
                name        = form.cleaned_data['name'],
                slug        = slug,
                brief_desc  = form.cleaned_data['brief_desc'] or meta.get('desc', ''),
                status      = form.cleaned_data['status'],
                min_players = form.cleaned_data['min_players'],
                max_players = form.cleaned_data['max_players'],
                pff_path    = str(game_dir),
                metadata_json = meta,
                owner       = request.user,
            )

            # 4. Notify WSZ6-play via internal API.
            _notify_play_game_installed(game)

            messages.success(request, f'"{game.name}" installed successfully.')
            logger.info('Game installed: %s (slug=%s) by %s', game.name, slug, request.user)

            if 'debug' in request.POST:
                return redirect('wsz6_play:debug_launch', game_slug=slug)
            return redirect('games_catalog:detail', slug=slug)
    else:
        form = GameInstallForm()

    return render(request, 'games_catalog/install.html', {'form': form})


def _notify_play_game_installed(game: Game):
    """POST to the internal API to tell WSZ6-play about the new game."""
    import urllib.request, urllib.error
    url     = 'http://127.0.0.1:8000/internal/v1/games/installed/'
    payload = json.dumps({'slug': game.slug, 'pff_path': game.pff_path}).encode()
    req     = urllib.request.Request(
        url, data=payload,
        headers={
            'Content-Type': 'application/json',
            'X-Internal-Api-Key': settings.INTERNAL_API_KEY,
        },
        method='POST',
    )
    try:
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        logger.warning('Could not notify WSZ6-play of game install: %s', e)
