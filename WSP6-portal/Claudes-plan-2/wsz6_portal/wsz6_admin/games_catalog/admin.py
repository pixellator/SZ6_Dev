from django.contrib import admin
from .models import Game


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display  = ('name', 'slug', 'status', 'min_players', 'max_players', 'installed_at')
    list_filter   = ('status',)
    search_fields = ('name', 'slug', 'brief_desc')
    readonly_fields = ('installed_at', 'updated_at', 'pff_path', 'metadata_json')
    prepopulated_fields = {'slug': ('name',)}
