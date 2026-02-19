"""
wsz6_admin/dashboard/views.py

Admin dashboard: home, user management, live sessions panel.
All views require login; most also require is_any_admin().
"""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone

from wsz6_admin.accounts.models import WSZUser
from wsz6_admin.accounts.forms import UserEditForm
from wsz6_admin.games_catalog.models import Game
from wsz6_admin.sessions_log.models import GameSession


def _is_admin(user):
    return user.is_authenticated and user.is_any_admin()


admin_required = user_passes_test(_is_admin, login_url='/accounts/login/')


@login_required
def home(request):
    """Dashboard home: summary stats and quick links."""
    ctx = {}
    if request.user.is_any_admin():
        ctx['user_count']    = WSZUser.objects.count()
        ctx['game_count']    = Game.objects.count()
        ctx['session_count'] = GameSession.objects.count()
        ctx['active_sessions'] = GameSession.objects.filter(
            status__in=[GameSession.STATUS_OPEN, GameSession.STATUS_IN_PROGRESS]
        ).select_related('game', 'owner')[:10]
        ctx['recent_games'] = Game.objects.order_by('-installed_at')[:5]
    return render(request, 'dashboard/home.html', ctx)


@admin_required
def user_list(request):
    """Searchable list of all WSZ users."""
    q = request.GET.get('q', '').strip()
    users = WSZUser.objects.order_by('username')
    if q:
        users = users.filter(
            Q(username__icontains=q) |
            Q(email__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        )
    # Annotate with session count
    users = users.annotate(session_count=Count('owned_sessions'))
    return render(request, 'dashboard/user_list.html', {'users': users, 'q': q})


@admin_required
def user_detail(request, pk):
    """View and edit a single user's WSZ6 settings."""
    target = get_object_or_404(WSZUser, pk=pk)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=target)
        if form.is_valid():
            form.save()
            messages.success(request, f"User '{target.username}' updated.")
            return redirect('dashboard:user_detail', pk=pk)
    else:
        form = UserEditForm(instance=target)

    sessions = GameSession.objects.filter(owner=target).select_related('game').order_by('-started_at')[:20]
    return render(request, 'dashboard/user_detail.html', {
        'target': target,
        'form': form,
        'sessions': sessions,
    })


@admin_required
def live_sessions(request):
    """Live view of currently open/in-progress game sessions."""
    active = GameSession.objects.filter(
        status__in=[GameSession.STATUS_OPEN, GameSession.STATUS_IN_PROGRESS]
    ).select_related('game', 'owner').order_by('-started_at')

    recent_ended = GameSession.objects.filter(
        status__in=[GameSession.STATUS_COMPLETED, GameSession.STATUS_INTERRUPTED],
        ended_at__gte=timezone.now() - timezone.timedelta(hours=1),
    ).select_related('game', 'owner').order_by('-ended_at')[:20]

    return render(request, 'dashboard/live_sessions.html', {
        'active': active,
        'recent_ended': recent_ended,
    })
