from django.contrib import admin
from .models import GameSession


@admin.register(GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display  = ('session_key', 'game', 'owner', 'status', 'started_at', 'ended_at')
    list_filter   = ('status', 'game')
    search_fields = ('session_key', 'owner__username', 'game__name')
    readonly_fields = ('session_key', 'started_at', 'summary_json', 'gdm_path')
