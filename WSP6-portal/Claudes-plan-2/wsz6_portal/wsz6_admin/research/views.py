"""
wsz6_admin/research/views.py

Research-panel views (Phase 5 — R1, R2, R3).

Access is restricted to users whose can_access_research() returns True
(ADMIN_RESEARCH and ADMIN_GENERAL).
"""

import json
import os

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from wsz6_admin.games_catalog.models import Game
from wsz6_admin.sessions_log.models import GameSession
from wsz6_play.models import PlayThrough


# ---------------------------------------------------------------------------
# Access guard
# ---------------------------------------------------------------------------

def _require_research(request):
    """Return a 403 response if the user cannot access the research panel."""
    if not request.user.can_access_research():
        return HttpResponseForbidden(
            "You don't have permission to access the research panel."
        )
    return None


# ---------------------------------------------------------------------------
# R1 — Session list dashboard
# ---------------------------------------------------------------------------

@login_required
def research_dashboard(request):
    """Filterable, paginated list of all game sessions."""
    guard = _require_research(request)
    if guard:
        return guard

    # ── Filters from query string ──────────────────────────────────────────
    game_slug = request.GET.get('game', '').strip()
    status    = request.GET.get('status', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to   = request.GET.get('date_to', '').strip()
    owner_q   = request.GET.get('owner', '').strip()

    qs = GameSession.objects.select_related('game', 'owner').order_by('-started_at')

    if game_slug:
        qs = qs.filter(game__slug=game_slug)
    if status:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(started_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(started_at__date__lte=date_to)
    if owner_q:
        qs = qs.filter(owner__username__icontains=owner_q)

    # ── Pagination ─────────────────────────────────────────────────────────
    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # ── Annotate each session with its playthrough count from GDM ──────────
    session_keys = [s.session_key for s in page_obj]
    pt_counts = {}
    if session_keys:
        try:
            rows = (
                PlayThrough.objects
                .using('gdm')
                .filter(session_key__in=session_keys)
                .values('session_key')
                .annotate(count=Count('playthrough_id'))
            )
            pt_counts = {str(r['session_key']): r['count'] for r in rows}
        except Exception:
            pass  # GDM unreachable; counts stay at 0

    for s in page_obj:
        s.playthrough_count = pt_counts.get(str(s.session_key), 0)

    # ── Filter params string for pagination links ───────────────────────────
    params = request.GET.copy()
    params.pop('page', None)
    filter_qs = params.urlencode()

    context = {
        'page_obj':       page_obj,
        'games':          Game.objects.order_by('name'),
        'game_slug':      game_slug,
        'status':         status,
        'date_from':      date_from,
        'date_to':        date_to,
        'owner_q':        owner_q,
        'status_choices': GameSession.STATUS_CHOICES,
        'filter_qs':      filter_qs,
        'total_count':    paginator.count,
    }
    return render(request, 'research/dashboard.html', context)


# ---------------------------------------------------------------------------
# R2 — Session detail
# ---------------------------------------------------------------------------

@login_required
def session_detail(request, session_key):
    """Session metadata + list of all play-throughs."""
    guard = _require_research(request)
    if guard:
        return guard

    session = get_object_or_404(
        GameSession.objects.select_related('game', 'owner'),
        session_key=session_key,
    )

    # Fetch play-throughs from GDM, numbered 1-based for display.
    try:
        playthroughs = list(
            PlayThrough.objects
            .using('gdm')
            .filter(session_key=session_key)
            .order_by('started_at')
        )
    except Exception:
        playthroughs = []

    for i, pt in enumerate(playthroughs):
        pt.display_num = i + 1

    return render(request, 'research/session_detail.html', {
        'session':      session,
        'playthroughs': playthroughs,
    })


# ---------------------------------------------------------------------------
# R3 — Log viewer
# ---------------------------------------------------------------------------

@login_required
def log_viewer(request, session_key, playthrough_id):
    """Step-by-step replay of a single play-through log."""
    guard = _require_research(request)
    if guard:
        return guard

    session = get_object_or_404(
        GameSession.objects.select_related('game', 'owner'),
        session_key=session_key,
    )

    # Fetch the PlayThrough record from GDM.
    try:
        pt = PlayThrough.objects.using('gdm').get(playthrough_id=playthrough_id)
    except PlayThrough.DoesNotExist:
        raise Http404("Play-through not found.")

    # ── Parse the JSONL log file ────────────────────────────────────────────
    log_entries = []
    log_error   = None

    if not pt.log_path:
        log_error = "No log path is recorded for this play-through."
    elif not os.path.isfile(pt.log_path):
        log_error = f"Log file not found on disk: {pt.log_path}"
    else:
        try:
            with open(pt.log_path, 'r', encoding='utf-8') as f:
                for i, raw_line in enumerate(f):
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        data = {'event': 'parse_error', 'raw': line}
                    # Pre-format any nested dicts as indented JSON strings
                    # so they can be dropped into <pre> tags in the template.
                    entry = {'index': i, 'data': data}
                    for key in ('state', 'role_assignments'):
                        if key in data:
                            try:
                                entry[f'{key}_json'] = json.dumps(
                                    data[key], indent=2, default=str
                                )
                            except Exception:
                                entry[f'{key}_json'] = str(data[key])
                    log_entries.append(entry)
        except OSError as exc:
            log_error = str(exc)

    # ── Pagination ─────────────────────────────────────────────────────────
    paginator = Paginator(log_entries, 50)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    # ── Prev / next play-through navigation ────────────────────────────────
    prev_pt = next_pt = pt_index = None
    try:
        all_pt_ids = list(
            PlayThrough.objects
            .using('gdm')
            .filter(session_key=session_key)
            .order_by('started_at')
            .values_list('playthrough_id', flat=True)
        )
        for i, pid in enumerate(all_pt_ids):
            if str(pid) == str(playthrough_id):
                pt_index = i + 1
                if i > 0:
                    prev_pt = all_pt_ids[i - 1]
                if i < len(all_pt_ids) - 1:
                    next_pt = all_pt_ids[i + 1]
                break
    except Exception:
        pass

    return render(request, 'research/log_viewer.html', {
        'session':       session,
        'pt':            pt,
        'pt_index':      pt_index,
        'prev_pt':       prev_pt,
        'next_pt':       next_pt,
        'page_obj':      page_obj,
        'log_error':     log_error,
        'total_entries': len(log_entries),
    })


# ---------------------------------------------------------------------------
# Export — JSONL download (R5 preview; trivial to include here)
# ---------------------------------------------------------------------------

@login_required
def export_jsonl(request, session_key, playthrough_id):
    """Serve the raw log.jsonl for a play-through as a file download."""
    guard = _require_research(request)
    if guard:
        return guard

    try:
        pt = PlayThrough.objects.using('gdm').get(playthrough_id=playthrough_id)
    except PlayThrough.DoesNotExist:
        raise Http404("Play-through not found.")

    if not pt.log_path or not os.path.isfile(pt.log_path):
        raise Http404("Log file not found on disk.")

    session = get_object_or_404(GameSession.objects.select_related('game'),
                                session_key=session_key)
    slug_short = session.game.slug[:20]
    key_short  = str(session_key).split('-')[0]
    filename   = f"{slug_short}-{key_short}-pt.jsonl"

    return FileResponse(
        open(pt.log_path, 'rb'),
        as_attachment=True,
        filename=filename,
        content_type='application/x-ndjson',
    )
