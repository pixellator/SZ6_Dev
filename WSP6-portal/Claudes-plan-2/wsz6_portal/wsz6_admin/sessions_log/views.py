"""wsz6_admin/sessions_log/views.py"""

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from .models import GameSession


@login_required
def session_list(request):
    q = request.GET.get('q', '').strip()
    user = request.user

    if user.is_any_admin():
        sessions = GameSession.objects.select_related('game', 'owner').order_by('-started_at')
    else:
        sessions = GameSession.objects.filter(owner=user).select_related('game').order_by('-started_at')

    if q:
        sessions = sessions.filter(
            Q(game__name__icontains=q) | Q(owner__username__icontains=q)
        )

    return render(request, 'sessions_log/list.html', {'sessions': sessions[:50], 'q': q})
