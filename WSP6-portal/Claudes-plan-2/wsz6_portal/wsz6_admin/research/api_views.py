"""
wsz6_admin/research/api_views.py

External REST API for the researcher panel (R7).

Authentication:
  • Bearer token  (ResearchTokenAuthentication)
  • Django session (SessionAuthentication — browser / Swagger)

Permission:
  • IsResearcher — requires can_access_research() == True

Endpoints:
  GET /api/v1/sessions/
  GET /api/v1/sessions/<key>/
  GET /api/v1/sessions/<key>/playthroughs/
  GET /api/v1/sessions/<key>/playthroughs/<pt_id>/
  GET /api/v1/sessions/<key>/playthroughs/<pt_id>/log/
  GET /api/v1/sessions/<key>/playthroughs/<pt_id>/log.jsonl
"""

import json
import os

from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from wsz6_admin.sessions_log.models import GameSession
from wsz6_play.models import PlayThrough

from .api_auth import ResearchTokenAuthentication
from .serializers import PlayThroughSerializer, SessionSerializer


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------

class IsResearcher(BasePermission):
    """Allow access only to users whose can_access_research() returns True."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and hasattr(user, 'can_access_research')
            and user.can_access_research()
        )


# ---------------------------------------------------------------------------
# Base mixin
# ---------------------------------------------------------------------------

_AUTH  = [ResearchTokenAuthentication, SessionAuthentication]
_PERMS = [IsResearcher]


class ResearchAPIView(APIView):
    authentication_classes = _AUTH
    permission_classes     = _PERMS


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

class APISessionListView(ResearchAPIView):
    """GET /api/v1/sessions/  — paginated, filterable session list."""

    def get(self, request):
        game_slug = request.GET.get('game',      '').strip()
        status    = request.GET.get('status',    '').strip()
        date_from = request.GET.get('date_from', '').strip()
        date_to   = request.GET.get('date_to',   '').strip()

        qs = (
            GameSession.objects
            .select_related('game', 'owner')
            .order_by('-started_at')
        )
        if game_slug:
            qs = qs.filter(game__slug=game_slug)
        if status:
            qs = qs.filter(status=status)
        if date_from:
            qs = qs.filter(started_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(started_at__date__lte=date_to)

        try:
            page_size = min(int(request.GET.get('page_size', 25)), 100)
        except (ValueError, TypeError):
            page_size = 25

        paginator = Paginator(qs, page_size)
        page      = paginator.get_page(request.GET.get('page', 1))

        serializer = SessionSerializer(list(page), many=True)
        return Response({
            'count':     paginator.count,
            'num_pages': paginator.num_pages,
            'page':      page.number,
            'results':   serializer.data,
        })


class APISessionDetailView(ResearchAPIView):
    """GET /api/v1/sessions/<key>/  — single session + playthrough count."""

    def get(self, request, session_key):
        session = get_object_or_404(
            GameSession.objects.select_related('game', 'owner'),
            session_key=session_key,
        )
        try:
            pt_count = (
                PlayThrough.objects
                .using('gdm')
                .filter(session_key=session_key)
                .count()
            )
        except Exception:
            pt_count = None

        data = SessionSerializer(session).data
        data['playthrough_count'] = pt_count
        return Response(data)


# ---------------------------------------------------------------------------
# Play-through endpoints
# ---------------------------------------------------------------------------

class APIPlayThroughListView(ResearchAPIView):
    """GET /api/v1/sessions/<key>/playthroughs/  — all play-throughs."""

    def get(self, request, session_key):
        get_object_or_404(GameSession, session_key=session_key)

        try:
            pts = list(
                PlayThrough.objects
                .using('gdm')
                .filter(session_key=session_key)
                .order_by('started_at')
            )
        except Exception:
            pts = []

        return Response({'results': PlayThroughSerializer(pts, many=True).data})


class APIPlayThroughDetailView(ResearchAPIView):
    """GET /api/v1/sessions/<key>/playthroughs/<pt_id>/  — single play-through."""

    def get(self, request, session_key, playthrough_id):
        get_object_or_404(GameSession, session_key=session_key)

        try:
            pt = PlayThrough.objects.using('gdm').get(playthrough_id=playthrough_id)
        except PlayThrough.DoesNotExist:
            raise Http404('Play-through not found.')

        return Response(PlayThroughSerializer(pt).data)


# ---------------------------------------------------------------------------
# Log endpoints
# ---------------------------------------------------------------------------

class APILogView(ResearchAPIView):
    """GET /api/v1/.../log/  — parsed log events as a JSON array."""

    def get(self, request, session_key, playthrough_id):
        get_object_or_404(GameSession, session_key=session_key)

        try:
            pt = PlayThrough.objects.using('gdm').get(playthrough_id=playthrough_id)
        except PlayThrough.DoesNotExist:
            raise Http404('Play-through not found.')

        if not pt.log_path or not os.path.isfile(pt.log_path):
            return Response({'error': 'Log file not found on disk.'}, status=404)

        entries = []
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
                    entries.append({'index': i, 'data': data})
        except OSError as exc:
            return Response({'error': str(exc)}, status=500)

        return Response({
            'playthrough_id': str(playthrough_id),
            'session_key':    str(session_key),
            'total_entries':  len(entries),
            'entries':        entries,
        })


class APILogRawView(ResearchAPIView):
    """GET /api/v1/.../log.jsonl  — raw JSONL file download."""

    def get(self, request, session_key, playthrough_id):
        session = get_object_or_404(
            GameSession.objects.select_related('game'),
            session_key=session_key,
        )

        try:
            pt = PlayThrough.objects.using('gdm').get(playthrough_id=playthrough_id)
        except PlayThrough.DoesNotExist:
            raise Http404('Play-through not found.')

        if not pt.log_path or not os.path.isfile(pt.log_path):
            raise Http404('Log file not found on disk.')

        slug_part = session.game.slug[:20]
        key_part  = str(session_key).split('-')[0]
        filename  = f'{slug_part}-{key_part}-pt.jsonl'

        return FileResponse(
            open(pt.log_path, 'rb'),
            as_attachment=True,
            filename=filename,
            content_type='application/x-ndjson',
        )
