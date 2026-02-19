"""games_catalog/views.py  –  stubs; full implementation in Phase 1."""
from django.shortcuts import render, get_object_or_404
from .models import Game


def game_list(request):
    games = Game.objects.filter(status=Game.STATUS_PUBLISHED)
    return render(request, 'games_catalog/list.html', {'games': games})


def game_detail(request, slug):
    game = get_object_or_404(Game, slug=slug)
    return render(request, 'games_catalog/detail.html', {'game': game})
