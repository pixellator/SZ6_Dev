"""sessions_log/views.py  –  stub; full implementation in Phase 1."""
from django.shortcuts import render

def session_list(request):
    return render(request, 'sessions_log/list.html', {})
