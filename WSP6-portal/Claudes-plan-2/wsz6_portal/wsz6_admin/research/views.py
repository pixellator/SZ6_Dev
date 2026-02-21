"""
wsz6_admin/research/views.py

Research-panel views (Phase 5 — R1–R7).

Access is restricted to users whose can_access_research() returns True
(ADMIN_RESEARCH and ADMIN_GENERAL).
"""

import io
import json
import os
import re
import uuid
import zipfile

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import (
    FileResponse, Http404, HttpResponse,
    HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from wsz6_admin.games_catalog.models import Game
from wsz6_admin.sessions_log.models import GameSession
from wsz6_play.models import PlayThrough

from .models import ResearchAnnotation, ResearchAPIToken


# ---------------------------------------------------------------------------
# Access guard
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Annotation export helpers
# ---------------------------------------------------------------------------

def _build_pt_annotations_data(researcher, session_key, playthrough_id):
    """Return a serialisable dict of all annotations for one play-through.

    Includes session-level notes (playthrough_id IS NULL) so that every
    per-PT download is fully self-contained.

    Structure:
        {
            "session_key": "...",
            "playthrough_id": "...",
            "researcher": "username",
            "exported_at": "<ISO>",
            "session_annotations":     [{"annotation": "...", "created_at": "..."}],
            "playthrough_annotations": [{"annotation": "...", "created_at": "..."}],
            "frame_annotations": [{"log_frame_index": N, "annotation": "...", "created_at": "..."}]
        }
    """
    from django.utils import timezone

    # Session-level notes (no playthrough_id).
    sess_rows = list(
        ResearchAnnotation.objects
        .filter(
            researcher=researcher,
            session_key=session_key,
            playthrough_id__isnull=True,
        )
        .order_by('created_at')
        .values('annotation', 'created_at')
    )

    # Play-through-level and frame-level notes.
    pt_rows = list(
        ResearchAnnotation.objects
        .filter(
            researcher=researcher,
            session_key=session_key,
            playthrough_id=playthrough_id,
        )
        .order_by('log_frame_index', 'created_at')
        .values('log_frame_index', 'annotation', 'created_at')
    )

    return {
        'session_key':    str(session_key),
        'playthrough_id': str(playthrough_id),
        'researcher':     researcher.username,
        'exported_at':    timezone.now().isoformat(),
        'session_annotations': [
            {'annotation': r['annotation'],
             'created_at': r['created_at'].isoformat()}
            for r in sess_rows
        ],
        'playthrough_annotations': [
            {'annotation': r['annotation'],
             'created_at': r['created_at'].isoformat()}
            for r in pt_rows if r['log_frame_index'] is None
        ],
        'frame_annotations': [
            {'log_frame_index': r['log_frame_index'],
             'annotation':      r['annotation'],
             'created_at':      r['created_at'].isoformat()}
            for r in pt_rows if r['log_frame_index'] is not None
        ],
    }


def _build_session_annotations_data(researcher, session_key):
    """Return a serialisable dict of session-level annotations only."""
    from django.utils import timezone

    rows = list(
        ResearchAnnotation.objects
        .filter(
            researcher=researcher,
            session_key=session_key,
            playthrough_id__isnull=True,
        )
        .order_by('created_at')
        .values('annotation', 'created_at')
    )
    return {
        'session_key': str(session_key),
        'researcher':  researcher.username,
        'exported_at': timezone.now().isoformat(),
        'session_annotations': [
            {'annotation': r['annotation'],
             'created_at': r['created_at'].isoformat()}
            for r in rows
        ],
    }

def _require_research(request):
    """Return a 403 response if the user cannot access the research panel."""
    if not request.user.can_access_research():
        return HttpResponseForbidden(
            "You don't have permission to access the research panel."
        )
    return None


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_SAFE_ARTIFACT_RE = re.compile(r'^[\w\-\.]+$')   # no slashes, no path separators
_VERSION_IN_PATH  = re.compile(r'\.v(\d+)\.')     # matches ".v2." in "essay.v2.txt"


def _playthrough_dir(pt):
    """Derive the play-through directory from the PlayThrough log_path."""
    return os.path.dirname(pt.log_path) if pt.log_path else None


def _session_dir(pt):
    """Derive the GDM session directory from the play-through log_path.

    log_path: .../sessions/<key>/playthroughs/<pt_id>/log.jsonl
    → session_dir: .../sessions/<key>/
    """
    pt_dir = _playthrough_dir(pt)
    if not pt_dir:
        return None
    # pt_dir = .../sessions/<key>/playthroughs/<pt_id>
    # parent = .../sessions/<key>/playthroughs
    # grandparent = .../sessions/<key>
    return os.path.dirname(os.path.dirname(pt_dir))


def _zip_dir(zf, disk_dir, zip_prefix):
    """Recursively add all files in disk_dir into the ZIP under zip_prefix."""
    if not os.path.isdir(disk_dir):
        return
    for fname in sorted(os.listdir(disk_dir)):
        fpath = os.path.join(disk_dir, fname)
        if os.path.isfile(fpath):
            zf.write(fpath, f"{zip_prefix}/{fname}")


def _safe_next(url, fallback='/research/'):
    """Return url only if it looks like a safe local redirect, else fallback."""
    url = (url or '').strip()
    if url.startswith('/') and not url.startswith('//') and ':' not in url:
        return url
    return fallback


# ---------------------------------------------------------------------------
# R1 — Session list dashboard
# ---------------------------------------------------------------------------

@login_required
def research_dashboard(request):
    """Filterable, paginated list of all game sessions."""
    guard = _require_research(request)
    if guard:
        return guard

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

    paginator = Paginator(qs, 25)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

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
            pass

    for s in page_obj:
        s.playthrough_count = pt_counts.get(str(s.session_key), 0)

    params = request.GET.copy()
    params.pop('page', None)
    filter_qs = params.urlencode()

    return render(request, 'research/dashboard.html', {
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
    })


# ---------------------------------------------------------------------------
# R2 — Session detail
# ---------------------------------------------------------------------------

@login_required
def session_detail(request, session_key):
    """Session metadata + list of all play-throughs + session-level annotations."""
    guard = _require_research(request)
    if guard:
        return guard

    session = get_object_or_404(
        GameSession.objects.select_related('game', 'owner'),
        session_key=session_key,
    )

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

    # Session-level annotations (this researcher, no playthrough_id)
    session_annotations = list(
        ResearchAnnotation.objects.filter(
            researcher=request.user,
            session_key=session_key,
            playthrough_id__isnull=True,
        )
    )

    return render(request, 'research/session_detail.html', {
        'session':             session,
        'playthroughs':        playthroughs,
        'session_annotations': session_annotations,
    })


# ---------------------------------------------------------------------------
# R3 — Log viewer
# ---------------------------------------------------------------------------

_ARTIFACT_EVENTS = ('artifact_created', 'artifact_saved', 'artifact_finalized')


def _enrich_log_entry(entry):
    """Pre-process one log entry dict in-place for template rendering.

    - Formats nested dicts (state, role_assignments) as indented JSON strings.
    - For artifact events, extracts artifact_name_safe and artifact_version
      so the template can build a fetch URL.
    """
    data = entry['data']
    for key in ('state', 'role_assignments'):
        if key in data:
            try:
                entry[f'{key}_json'] = json.dumps(data[key], indent=2, default=str)
            except Exception:
                entry[f'{key}_json'] = str(data[key])

    ev = data.get('event', '')
    if ev in _ARTIFACT_EVENTS:
        artifact_name = data.get('artifact_name', '')
        artifact_path = data.get('artifact_path', '')
        version = data.get('version') or data.get('final_version')
        # Fall back to parsing the version from the filename in artifact_path
        if version is None and artifact_path:
            m = _VERSION_IN_PATH.search(artifact_path)
            if m:
                version = int(m.group(1))
        entry['artifact_name_safe'] = artifact_name
        entry['artifact_version']   = version


@login_required
def log_viewer(request, session_key, playthrough_id):
    """Step-by-step replay of a single play-through log, with annotations."""
    guard = _require_research(request)
    if guard:
        return guard

    session = get_object_or_404(
        GameSession.objects.select_related('game', 'owner'),
        session_key=session_key,
    )

    try:
        pt = PlayThrough.objects.using('gdm').get(playthrough_id=playthrough_id)
    except PlayThrough.DoesNotExist:
        raise Http404("Play-through not found.")

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
                    entry = {'index': i, 'data': data}
                    _enrich_log_entry(entry)
                    log_entries.append(entry)
        except OSError as exc:
            log_error = str(exc)

    # Load annotations for this play-through.
    pt_annotations = []
    if not log_error:
        try:
            all_anns = list(
                ResearchAnnotation.objects.filter(
                    researcher=request.user,
                    session_key=session_key,
                    playthrough_id=playthrough_id,
                )
            )
            pt_annotations = [a for a in all_anns if a.log_frame_index is None]
            frame_anns = {}
            for a in all_anns:
                if a.log_frame_index is not None:
                    frame_anns.setdefault(a.log_frame_index, []).append(a)
            for entry in log_entries:
                entry['annotations'] = frame_anns.get(entry['index'], [])
        except Exception:
            for entry in log_entries:
                entry['annotations'] = []

    paginator = Paginator(log_entries, 50)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

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
        'session':         session,
        'pt':              pt,
        'pt_index':        pt_index,
        'prev_pt':         prev_pt,
        'next_pt':         next_pt,
        'page_obj':        page_obj,
        'log_error':       log_error,
        'total_entries':   len(log_entries),
        'pt_annotations':  pt_annotations,
    })


# ---------------------------------------------------------------------------
# R4 — Artifact viewer
# ---------------------------------------------------------------------------

@login_required
def artifact_viewer(request, session_key, playthrough_id, artifact_name):
    """Serve an artifact file, either as HTML or as JSON for AJAX loading.

    Query params:
        version — integer version number; if absent serves the "current" file
        format  — if "json" returns {"name", "content", "version", "path"}
    """
    guard = _require_research(request)
    if guard:
        return guard

    # Validate artifact_name to prevent path traversal.
    if not _SAFE_ARTIFACT_RE.match(artifact_name):
        raise Http404("Invalid artifact name.")

    try:
        pt = PlayThrough.objects.using('gdm').get(playthrough_id=playthrough_id)
    except PlayThrough.DoesNotExist:
        raise Http404("Play-through not found.")

    pt_dir = _playthrough_dir(pt)
    if not pt_dir:
        raise Http404("Play-through has no log path.")

    artifacts_dir = os.path.realpath(os.path.join(pt_dir, 'artifacts'))
    version_param = request.GET.get('version', '').strip()

    if version_param:
        try:
            version = int(version_param)
        except ValueError:
            raise Http404("Invalid version number.")
        filename = f"{artifact_name}.v{version}.txt"
    else:
        filename = f"{artifact_name}.txt"
        version  = None

    # Security: resolve and confirm the target is inside artifacts_dir.
    artifact_path = os.path.realpath(os.path.join(artifacts_dir, filename))
    if not artifact_path.startswith(artifacts_dir + os.sep) and artifact_path != artifacts_dir:
        raise Http404("Access denied.")

    if not os.path.isfile(artifact_path):
        raise Http404(f"Artifact file not found: {filename}")

    try:
        with open(artifact_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError as exc:
        raise Http404(str(exc))

    if request.GET.get('format') == 'json':
        return JsonResponse({
            'name':    artifact_name,
            'version': version,
            'path':    filename,
            'content': content,
        })

    # HTML page view (for direct navigation)
    session = get_object_or_404(
        GameSession.objects.select_related('game', 'owner'),
        session_key=session_key,
    )
    return render(request, 'research/artifact_viewer.html', {
        'session':       session,
        'pt':            pt,
        'artifact_name': artifact_name,
        'version':       version,
        'content':       content,
        'filename':      filename,
    })


# ---------------------------------------------------------------------------
# R5 — Export: JSONL + ZIP variants
# ---------------------------------------------------------------------------

@login_required
def export_jsonl(request, session_key, playthrough_id):
    """Serve the raw log.jsonl for a play-through.

    If ?include_annotations=1, bundles log.jsonl + annotations.json into a
    small ZIP (since two files cannot be streamed as one download).
    Otherwise serves the bare JSONL.
    """
    guard = _require_research(request)
    if guard:
        return guard

    try:
        pt = PlayThrough.objects.using('gdm').get(playthrough_id=playthrough_id)
    except PlayThrough.DoesNotExist:
        raise Http404("Play-through not found.")

    if not pt.log_path or not os.path.isfile(pt.log_path):
        raise Http404("Log file not found on disk.")

    session   = get_object_or_404(GameSession.objects.select_related('game'),
                                  session_key=session_key)
    slug_part = session.game.slug[:20]
    key_part  = str(session_key).split('-')[0]

    include_annotations = request.GET.get('include_annotations', '0') == '1'

    if include_annotations:
        # Bundle log.jsonl + annotations.json into a small ZIP.
        ann_data = _build_pt_annotations_data(request.user, session_key, playthrough_id)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(pt.log_path, 'log.jsonl')
            zf.writestr('annotations.json',
                        json.dumps(ann_data, default=str, indent=2))
        buf.seek(0)
        filename = f"{slug_part}-{key_part}-pt-annotated.zip"
        response = HttpResponse(buf.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    filename = f"{slug_part}-{key_part}-pt.jsonl"
    return FileResponse(
        open(pt.log_path, 'rb'),
        as_attachment=True,
        filename=filename,
        content_type='application/x-ndjson',
    )


@login_required
def export_zip(request, session_key, playthrough_id):
    """ZIP download: log.jsonl + artifacts/ + checkpoints/ for one play-through.

    If ?include_annotations=1, also adds annotations.json to the archive.
    """
    guard = _require_research(request)
    if guard:
        return guard

    try:
        pt = PlayThrough.objects.using('gdm').get(playthrough_id=playthrough_id)
    except PlayThrough.DoesNotExist:
        raise Http404("Play-through not found.")

    pt_dir = _playthrough_dir(pt)
    if not pt_dir:
        raise Http404("Play-through has no log path.")

    session   = get_object_or_404(GameSession.objects.select_related('game'),
                                  session_key=session_key)
    slug_part = session.game.slug[:20]
    key_part  = str(session_key).split('-')[0]
    filename  = f"{slug_part}-{key_part}-pt.zip"

    include_annotations = request.GET.get('include_annotations', '0') == '1'

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        if pt.log_path and os.path.isfile(pt.log_path):
            zf.write(pt.log_path, 'log.jsonl')
        _zip_dir(zf, os.path.join(pt_dir, 'artifacts'),   'artifacts')
        _zip_dir(zf, os.path.join(pt_dir, 'checkpoints'), 'checkpoints')
        if include_annotations:
            ann_data = _build_pt_annotations_data(
                request.user, session_key, playthrough_id
            )
            zf.writestr('annotations.json',
                        json.dumps(ann_data, default=str, indent=2))
    buf.seek(0)

    response = HttpResponse(buf.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_session_zip(request, session_key):
    """ZIP download: all play-throughs for an entire session.

    Directory layout inside the ZIP:
        session_meta.json  (if present on disk)
        pt1/
            log.jsonl
            artifacts/
            checkpoints/
        pt2/
            ...
    """
    guard = _require_research(request)
    if guard:
        return guard

    session = get_object_or_404(
        GameSession.objects.select_related('game'),
        session_key=session_key,
    )

    try:
        playthroughs = list(
            PlayThrough.objects
            .using('gdm')
            .filter(session_key=session_key)
            .order_by('started_at')
        )
    except Exception:
        playthroughs = []

    slug_part = session.game.slug[:20]
    key_part  = str(session_key).split('-')[0]
    filename  = f"{slug_part}-{key_part}-session.zip"

    include_annotations = request.GET.get('include_annotations', '0') == '1'

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for i, pt in enumerate(playthroughs, start=1):
            prefix = f"pt{i}"
            pt_dir = _playthrough_dir(pt)
            if not pt_dir:
                continue
            if pt.log_path and os.path.isfile(pt.log_path):
                zf.write(pt.log_path, f"{prefix}/log.jsonl")
            _zip_dir(zf, os.path.join(pt_dir, 'artifacts'),   f"{prefix}/artifacts")
            _zip_dir(zf, os.path.join(pt_dir, 'checkpoints'), f"{prefix}/checkpoints")
            if include_annotations:
                ann_data = _build_pt_annotations_data(
                    request.user, session_key, pt.playthrough_id
                )
                zf.writestr(f"{prefix}/annotations.json",
                            json.dumps(ann_data, default=str, indent=2))

        # Include session_meta.json if present (one level above playthroughs/).
        if playthroughs and playthroughs[0].log_path:
            s_dir = _session_dir(playthroughs[0])
            if s_dir:
                meta_path = os.path.join(s_dir, 'session_meta.json')
                if os.path.isfile(meta_path):
                    zf.write(meta_path, 'session_meta.json')

        if include_annotations:
            sess_ann_data = _build_session_annotations_data(request.user, session_key)
            zf.writestr('session_annotations.json',
                        json.dumps(sess_ann_data, default=str, indent=2))

    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ---------------------------------------------------------------------------
# R6 — Researcher annotations
# ---------------------------------------------------------------------------

@login_required
def add_annotation(request):
    """POST-only: create a ResearchAnnotation and redirect back."""
    guard = _require_research(request)
    if guard:
        return guard
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    next_url       = _safe_next(request.POST.get('next', ''))
    session_key    = request.POST.get('session_key', '').strip()
    playthrough_id = request.POST.get('playthrough_id', '').strip() or None
    frame_idx      = request.POST.get('log_frame_index', '').strip() or None
    annotation     = request.POST.get('annotation', '').strip()

    if not session_key or not annotation:
        return redirect(next_url)

    kwargs = {
        'researcher':  request.user,
        'session_key': session_key,
        'annotation':  annotation,
    }
    if playthrough_id:
        kwargs['playthrough_id'] = playthrough_id
    if frame_idx is not None:
        try:
            kwargs['log_frame_index'] = int(frame_idx)
        except ValueError:
            pass

    ResearchAnnotation.objects.create(**kwargs)
    return redirect(next_url)


@login_required
def delete_annotation(request, pk):
    """POST-only: delete a ResearchAnnotation owned by this researcher."""
    guard = _require_research(request)
    if guard:
        return guard
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    next_url = _safe_next(request.POST.get('next', ''))
    ann = get_object_or_404(ResearchAnnotation, pk=pk, researcher=request.user)
    ann.delete()
    return redirect(next_url)


@login_required
def annotation_list(request):
    """All annotations for the current researcher, newest first."""
    guard = _require_research(request)
    if guard:
        return guard

    annotations = (
        ResearchAnnotation.objects
        .filter(researcher=request.user)
        .order_by('-created_at')
    )
    return render(request, 'research/annotations.html', {
        'annotations': annotations,
    })


# ---------------------------------------------------------------------------
# R6/R7 — API token management
# ---------------------------------------------------------------------------

@login_required
def api_token_page(request):
    """Show the researcher's API token (masked) with reveal/regenerate actions."""
    guard = _require_research(request)
    if guard:
        return guard

    try:
        token_obj = request.user.research_api_token
    except ResearchAPIToken.DoesNotExist:
        token_obj = None

    return render(request, 'research/api_token.html', {
        'token_obj': token_obj,
    })


@login_required
def regenerate_api_token(request):
    """POST-only: create or regenerate the researcher's API token."""
    guard = _require_research(request)
    if guard:
        return guard
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    token_obj, created = ResearchAPIToken.objects.get_or_create(
        researcher=request.user
    )
    if not created:
        # Regenerate the token UUID.
        token_obj.token     = uuid.uuid4()
        token_obj.is_active = True
        token_obj.save(update_fields=['token', 'is_active'])

    return redirect(reverse('research:api_token'))
